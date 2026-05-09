"""Cliente HTTP async para la API de Mercado Público (ChileCompra).

CLAUDE.md §9 y reglas de oro:
- Toda llamada a la API pasa por este cliente — nunca httpx directo.
- Rate limit interno: máximo 5 req/segundo por ticket.
- Retries: max 3 intentos, backoff exponencial (2x, max 30s), solo en 429/5xx/timeout.
- Cuota: 10.000 requests/día por ticket — loggear TODO en api_quota_log.
- Sin PII en logs: nunca loggear el ticket en claro, ni fragmentos.
- Formato fecha: ddmmaaaa (usar format_fecha_api() siempre).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date, datetime
import time
from typing import Any
import uuid

from aiolimiter import AsyncLimiter
import httpx
import structlog
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.schemas.chilecompra import (
    LicitacionDetalleResponseAPI,
    LicitacionesListadoResponseAPI,
)
from app.services.chilecompra.enums import EstadoLicitacion
from app.services.chilecompra.exceptions import (
    CuotaExcedidaError,
    LicitacionNoEncontradaError,
    MercadoPublicoError,
    RateLimitError,
    TicketInvalidoError,
)
from app.services.chilecompra.exceptions import TimeoutError as MPTimeoutError
from app.services.chilecompra.utils import format_fecha_api

logger = structlog.get_logger()

# URL base de la API de Mercado Público
_BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico"

# Rate limit: 5 req/segundo (CLAUDE.md §5 regla 18)
_RATE_LIMITER = AsyncLimiter(max_rate=5, time_period=1.0)

# Excepciones que justifican un retry
_RETRY_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    RateLimitError,
    MercadoPublicoError,  # 5xx
)


def _is_retryable(exc: BaseException) -> bool:
    """Determina si una excepción justifica reintentar."""
    if isinstance(exc, httpx.TimeoutException | httpx.ConnectError):
        return True
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, MercadoPublicoError) and exc.status_code is not None:
        return exc.status_code >= 500
    return False


class MercadoPublicoClient:
    """Cliente async para la API de Mercado Público.

    Uso con async context manager:
        async with MercadoPublicoClient(db_session) as client:
            licitaciones = await client.listar_licitaciones_por_estado(
                estado=EstadoLicitacion.ACTIVAS,
                ticket="F8537A18-...",
                ticket_id=uuid,
                empresa_id=uuid,
            )

    Atributos:
        session: AsyncSession de SQLAlchemy para loggear a api_quota_log.
    """

    def __init__(self) -> None:
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "MercadoPublicoClient":
        self._http = httpx.AsyncClient(
            base_url=_BASE_URL,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"Accept": "application/json"},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    @property
    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError(
                "MercadoPublicoClient debe usarse como async context manager"
            )
        return self._http

    async def _request(
        self,
        endpoint: str,
        params: dict[str, str],
        ticket: str,
        ticket_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Ejecuta un request con rate limit, retries y logging a api_quota_log.

        Args:
            endpoint: Path relativo, ej: "/licitaciones.json"
            params: Query params (sin el ticket — se agrega aquí)
            ticket: Ticket en texto claro (SOLO en memoria, NO loggear)
            ticket_id: FK para el log de cuota
            empresa_id: FK para el log de cuota

        Returns:
            Dict con el JSON de respuesta.

        Raises:
            TicketInvalidoError: 401/403
            RateLimitError: 429
            CuotaExcedidaError: cuota agotada (mensaje específico de la API)
            LicitacionNoEncontradaError: 404
            MPTimeoutError: timeout
            MercadoPublicoError: cualquier otro error 5xx
        """
        # El ticket va en params — NUNCA en logs
        all_params = {**params, "ticket": ticket}

        # Params seguros para loggear (sin ticket)
        safe_params = dict(params.items())

        start_ms = int(time.monotonic() * 1000)
        status_code: int | None = None
        error_msg: str | None = None

        try:
            async with _RATE_LIMITER:
                response = await self._request_with_retry(endpoint, all_params)

            status_code = response.status_code
            elapsed_ms = int(time.monotonic() * 1000) - start_ms

            self._raise_for_status(response, ticket)

            data: dict[str, Any] = response.json()
            return data

        except httpx.TimeoutException as e:
            elapsed_ms = int(time.monotonic() * 1000) - start_ms
            error_msg = f"Timeout: {e}"
            logger.warning(
                "chilecompra_timeout",
                endpoint=endpoint,
                params=safe_params,
                elapsed_ms=elapsed_ms,
            )
            raise MPTimeoutError(endpoint) from e

        except (
            TicketInvalidoError,
            RateLimitError,
            CuotaExcedidaError,
            LicitacionNoEncontradaError,
            MercadoPublicoError,
        ) as e:
            elapsed_ms = int(time.monotonic() * 1000) - start_ms
            error_msg = str(e)
            raise

        finally:
            elapsed_ms = int(time.monotonic() * 1000) - start_ms
            await self._log_request(
                endpoint=endpoint,
                params=safe_params,
                status_code=status_code,
                elapsed_ms=elapsed_ms,
                error_msg=error_msg,
                ticket_id=ticket_id,
                empresa_id=empresa_id,
            )

    async def _request_with_retry(
        self, endpoint: str, params: dict[str, str]
    ) -> httpx.Response:
        """Ejecuta el request HTTP con retries via tenacity."""

        @retry(
            retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=2, min=2, max=30),
            reraise=True,
        )
        async def _do_request() -> httpx.Response:
            return await self._client.get(endpoint, params=params)

        try:
            return await _do_request()
        except RetryError as e:
            raise MercadoPublicoError(f"Máximos reintentos agotados: {e}") from e

    def _raise_for_status(self, response: httpx.Response, ticket: str) -> None:
        """Convierte códigos HTTP en excepciones tipadas."""
        code = response.status_code

        if code == 200:
            # Verificar si la API indica cuota agotada en el body
            try:
                body = response.json()
                if isinstance(body, dict):
                    raw = body.get("mensaje", "") or body.get("Mensaje", "")
                    msg = str(raw).lower()
                    if "cuota" in msg or "excedido" in msg:
                        raise CuotaExcedidaError()
            except (ValueError, KeyError):
                pass
            return

        # Sin PII: los últimos 4 chars del ticket para el mensaje de error
        ultimos_4 = ticket[-4:] if len(ticket) >= 4 else "????"

        if code in (401, 403):
            raise TicketInvalidoError(ultimos_4)
        if code == 404:
            raise LicitacionNoEncontradaError("desconocido")
        if code == 429:
            retry_after = None
            import contextlib

            with contextlib.suppress(ValueError, TypeError):
                retry_after = int(response.headers.get("Retry-After", 0))
            raise RateLimitError(retry_after)
        if code >= 500:
            raise MercadoPublicoError(
                f"Error del servidor ChileCompra: HTTP {code}", status_code=code
            )

        raise MercadoPublicoError(f"HTTP {code} inesperado", status_code=code)

    async def _log_request(
        self,
        endpoint: str,
        params: dict[str, str],
        status_code: int | None,
        elapsed_ms: int,
        error_msg: str | None,
        ticket_id: uuid.UUID | None,
        empresa_id: uuid.UUID | None,
    ) -> None:
        """Persiste el request en api_quota_log. Import lazy para evitar ciclos."""
        try:
            from app.db.session import AsyncSessionLocal
            from app.models.api_log import ApiQuotaLog

            log = ApiQuotaLog(
                ticket_id=ticket_id,
                empresa_id=empresa_id,
                endpoint=endpoint,
                metodo="GET",
                status_code=status_code,
                duracion_ms=elapsed_ms,
                request_params=params,  # safe_params — sin ticket
                error_mensaje=error_msg,
            )
            async with AsyncSessionLocal() as session:
                session.add(log)
                await session.commit()
        except Exception as e:
            # Logging fallido no debe interrumpir el flujo principal
            logger.error("api_quota_log_failed", error=str(e))

    # ================================================================
    # Métodos públicos
    # ================================================================

    async def listar_licitaciones_por_estado(
        self,
        estado: EstadoLicitacion,
        ticket: str,
        ticket_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> LicitacionesListadoResponseAPI:
        """Lista licitaciones por estado (activas, publicada, cerrada, etc.).

        Args:
            estado: EstadoLicitacion.ACTIVAS para las del día actual.
            ticket: Ticket en texto claro (descifrado en memoria).
            ticket_id: Para loggear en api_quota_log.
            empresa_id: Para loggear en api_quota_log.

        Returns:
            LicitacionesListadoResponseAPI con Cantidad y Listado.
        """
        data = await self._request(
            endpoint="/licitaciones.json",
            params={"estado": estado.query_string},
            ticket=ticket,
            ticket_id=ticket_id,
            empresa_id=empresa_id,
        )
        return LicitacionesListadoResponseAPI.model_validate(data)

    async def listar_licitaciones_por_fecha(
        self,
        fecha: date | datetime,
        ticket: str,
        ticket_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> LicitacionesListadoResponseAPI:
        """Lista licitaciones publicadas en una fecha específica.

        CLAUDE.md §9 — trampa #1: formato ddmmaaaa sin separadores.

        Args:
            fecha: La fecha a consultar.
            ticket: Ticket en texto claro.
        """
        fecha_str = format_fecha_api(fecha)
        data = await self._request(
            endpoint="/licitaciones.json",
            params={"fecha": fecha_str},
            ticket=ticket,
            ticket_id=ticket_id,
            empresa_id=empresa_id,
        )
        return LicitacionesListadoResponseAPI.model_validate(data)

    async def obtener_detalle_licitacion(
        self,
        codigo: str,
        ticket: str,
        ticket_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> LicitacionDetalleResponseAPI:
        """Obtiene el detalle completo de una licitación por su código.

        Patrón obligatorio (CLAUDE.md §9): lista → detalle.
        Este endpoint es la segunda llamada del patrón.

        Args:
            codigo: Código de licitación, ej: "1000-8-LE26".
            ticket: Ticket en texto claro.

        Raises:
            LicitacionNoEncontradaError: Si el código no existe.
        """
        data = await self._request(
            endpoint="/licitaciones.json",
            params={"codigo": codigo},
            ticket=ticket,
            ticket_id=ticket_id,
            empresa_id=empresa_id,
        )
        response = LicitacionDetalleResponseAPI.model_validate(data)
        if response.Cantidad == 0 or not response.Listado:
            raise LicitacionNoEncontradaError(codigo)
        return response

    async def listar_ordenes_compra_por_fecha(
        self,
        fecha: date | datetime,
        ticket: str,
        ticket_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Lista órdenes de compra emitidas en una fecha.

        Retorna el dict crudo — el schema de OC se implementa en Sprint 2.
        """
        fecha_str = format_fecha_api(fecha)
        return await self._request(
            endpoint="/ordenes.json",
            params={"fecha": fecha_str},
            ticket=ticket,
            ticket_id=ticket_id,
            empresa_id=empresa_id,
        )


@asynccontextmanager
async def get_mp_client() -> AsyncGenerator[MercadoPublicoClient, None]:
    """Context manager de conveniencia para inyectar el cliente."""
    async with MercadoPublicoClient() as client:
        yield client
