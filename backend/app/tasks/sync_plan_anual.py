"""Tarea Celery: sincronización mensual del Plan Anual de Compras (PAC).

El plan anual es publicado por cada organismo del Estado en Mercado Público
y anticipa las licitaciones que planean emitir durante el año.

Endpoint de la API:
    GET https://api.mercadopublico.cl/api/v2/plancompra/GetPlanCompra
    Params: ticket, anio, pagina, cantidad

Reglas de oro que aplican:
- #2:  Tickets descifrados solo en memoria, nunca persistir en claro.
- #12: Sin PII en logs — nunca loggear el ticket.
- #17: Bulk loads en horario nocturno (22:00–07:00 CLT).
- #18: Rate limit 5 req/s, backoff exponencial en 429/5xx.
- #29: Tarea idempotente — upsert por (codigo_organismo, ano, descripcion).
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from app.celery_app import celery_app
from app.core.encryption import decrypt_ticket
from app.models.enums import PlanAnualStatus, TicketStatus

logger = structlog.get_logger()

# URL base del endpoint v2 del plan anual (distinto al v1 de licitaciones)
_PAC_BASE_URL = "https://api.mercadopublico.cl"
_PAC_ENDPOINT = "/api/v2/plancompra/GetPlanCompra"

# Cantidad de ítems por página (máximo soportado por la API)
_PAGE_SIZE = 100

# Pausa entre páginas para respetar el rate limit de 5 req/s
_SLEEP_ENTRE_PAGINAS = 0.2  # 200ms → ~5 req/s

# Mapeo del campo Estado de la API al enum interno PlanAnualStatus
_STATUS_MAP: dict[str, PlanAnualStatus] = {
    "Planificada": PlanAnualStatus.planificada,
    "Publicada": PlanAnualStatus.publicada,
    "Adjudicada": PlanAnualStatus.adjudicada,
    "Cancelada": PlanAnualStatus.cancelada,
}


def _mapear_status(estado_api: str | None) -> PlanAnualStatus:
    """Convierte el estado textual de la API al enum interno.

    Fallback a 'planificada' para valores desconocidos.
    """
    if estado_api is None:
        return PlanAnualStatus.planificada
    return _STATUS_MAP.get(estado_api, PlanAnualStatus.planificada)


async def _get_pagina_plan_anual(
    http: httpx.AsyncClient,
    ticket_plaintext: str,
    ano: int,
    pagina: int,
) -> dict[str, Any]:
    """Descarga una página del plan anual desde la API de ChileCompra.

    Implementa backoff exponencial ante 429 y 5xx.
    Regla de oro #18: rate limit activo.

    Args:
        http: Cliente httpx ya inicializado.
        ticket_plaintext: Ticket en texto claro (NUNCA loggear).
        ano: Año del plan a consultar.
        pagina: Número de página (base 1).

    Returns:
        Dict con la respuesta JSON cruda de la API.

    Raises:
        httpx.HTTPStatusError: En errores no recuperables.
    """
    params = {
        "ticket": ticket_plaintext,
        "anio": str(ano),
        "pagina": str(pagina),
        "cantidad": str(_PAGE_SIZE),
    }

    max_reintentos = 3
    espera = 1.0  # segundos, se duplica en cada reintento (1s, 2s, 4s)
    response: httpx.Response | None = None

    for intento in range(max_reintentos + 1):
        response = await http.get(_PAC_ENDPOINT, params=params)

        if response.status_code == 200:
            return response.json()  # type: ignore[return-value]

        if response.status_code == 429:
            # Rate limit de ChileCompra — esperar 60s antes de reintentar
            logger.warning(
                "plan_anual_rate_limit",
                ano=ano,
                pagina=pagina,
                intento=intento,
            )
            await asyncio.sleep(60.0)
            continue

        if response.status_code >= 500:
            if intento >= max_reintentos:
                logger.error(
                    "plan_anual_api_5xx_max_reintentos",
                    ano=ano,
                    pagina=pagina,
                    status_code=response.status_code,
                )
                response.raise_for_status()

            logger.warning(
                "plan_anual_api_5xx_reintentando",
                ano=ano,
                pagina=pagina,
                status_code=response.status_code,
                espera_s=espera,
            )
            await asyncio.sleep(espera)
            espera *= 2  # backoff exponencial
            continue

        # Errores 4xx no recuperables (401, 403, 404)
        response.raise_for_status()

    # Fallback defensivo — la lógica de arriba cubre todos los casos
    if response is not None:
        response.raise_for_status()
    raise RuntimeError("_get_pagina_plan_anual: máximos reintentos agotados sin respuesta")  # pragma: no cover


async def _upsert_organismo_si_falta(
    session: Any,
    codigo_organismo: int,
) -> None:
    """Inserta el organismo en la tabla si no existe, para evitar FK violation.

    Usa un nombre placeholder — el detalle real se actualiza en sync_detalle.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.organismo import Organismo

    stmt = (
        pg_insert(Organismo)
        .values(
            codigo_organismo=codigo_organismo,
            nombre=f"Organismo {codigo_organismo}",
        )
        .on_conflict_do_nothing(index_elements=["codigo_organismo"])
    )
    await session.execute(stmt)


async def _upsert_lineas(
    session: Any,
    lineas: list[dict[str, Any]],
    codigo_organismo: int,
    ano: int,
) -> int:
    """Hace upsert de una lista de líneas del plan anual.

    Clave de conflicto: (codigo_organismo, ano, descripcion).
    Actualiza todos los campos excepto id y created_at.
    Regla de oro #29: re-ejecutar no duplica filas.

    Prerequisito de BD:
        Debe existir la restricción única:
        UNIQUE (codigo_organismo, ano, descripcion) con nombre
        uq_plan_anual_organismo_ano_descripcion
        Crear con migración Alembic si todavía no existe.

    Returns:
        Cantidad de filas procesadas en el upsert.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.plan_anual import PlanAnualLinea

    ahora = datetime.now(UTC)
    registros: list[dict[str, Any]] = []

    for item in lineas:
        descripcion = item.get("Descripcion") or ""
        if not descripcion:
            # Sin descripción no se puede construir la clave de conflicto — saltar
            continue

        status = _mapear_status(item.get("Estado"))

        registros.append(
            {
                "ano": ano,
                "codigo_organismo": codigo_organismo,
                "descripcion": descripcion,
                "unspsc_codigo": None,  # sin validación de FK — se deja NULL
                "unspsc_nombre": item.get("NombreProducto"),
                "monto_estimado": item.get("MontoEstimado"),
                "moneda": item.get("Moneda") or "CLP",
                "mes_estimado": item.get("MesEstimado"),
                "modalidad": item.get("Modalidad"),
                "status": status,
                "raw_payload": item,
                "updated_at": ahora,
            }
        )

    if not registros:
        return 0

    # Construir el INSERT … ON CONFLICT DO UPDATE.
    # stmt.excluded accede a la pseudo-tabla "excluded" de PostgreSQL, que
    # contiene los valores que habrían sido insertados en caso de conflicto.
    insert_stmt = pg_insert(PlanAnualLinea).values(registros)
    upsert_stmt = insert_stmt.on_conflict_do_update(
        constraint="uq_plan_anual_organismo_ano_descripcion",
        set_={
            "unspsc_nombre": insert_stmt.excluded.unspsc_nombre,
            "monto_estimado": insert_stmt.excluded.monto_estimado,
            "moneda": insert_stmt.excluded.moneda,
            "mes_estimado": insert_stmt.excluded.mes_estimado,
            "modalidad": insert_stmt.excluded.modalidad,
            "status": insert_stmt.excluded.status,
            "raw_payload": insert_stmt.excluded.raw_payload,
            "updated_at": insert_stmt.excluded.updated_at,
        },
    )
    await session.execute(upsert_stmt)
    return len(registros)


async def _sync_plan_empresa(
    empresa_id: str,
    ticket_cifrado: str,
    ticket_id: str,
    anos: list[int],
) -> dict[str, int]:
    """Sincroniza el plan anual de una empresa para los años indicados.

    Args:
        empresa_id: ID interno de la empresa (solo para logs — regla #12).
        ticket_cifrado: Ticket cifrado en BD.
        ticket_id: ID del ticket (para trazabilidad en logs).
        anos: Lista de años a sincronizar.

    Returns:
        Dict con contadores: upserted, paginas, errores.
    """
    from app.db.session import AsyncSessionLocal

    stats: dict[str, int] = {"upserted": 0, "paginas": 0, "errores": 0}

    # Descifrar solo en memoria — regla de oro #2
    try:
        ticket_plaintext = decrypt_ticket(ticket_cifrado)
    except Exception as e:
        logger.error(
            "plan_anual_ticket_decrypt_failed",
            empresa_id=empresa_id,
            error=str(e),
        )
        stats["errores"] += 1
        return stats

    try:
        async with httpx.AsyncClient(
            base_url=_PAC_BASE_URL,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"Accept": "application/json"},
            follow_redirects=True,
        ) as http:
            for ano in anos:
                pagina = 1
                log = logger.bind(empresa_id=empresa_id, ano=ano)

                while True:
                    try:
                        data = await _get_pagina_plan_anual(
                            http=http,
                            ticket_plaintext=ticket_plaintext,
                            ano=ano,
                            pagina=pagina,
                        )
                    except httpx.HTTPStatusError as e:
                        log.error(
                            "plan_anual_pagina_error",
                            pagina=pagina,
                            error=str(e),
                            status_code=e.response.status_code,
                        )
                        stats["errores"] += 1
                        break

                    listado: list[dict[str, Any]] = data.get("Listado") or []
                    stats["paginas"] += 1

                    log.info(
                        "plan_anual_pagina_ok",
                        pagina=pagina,
                        items=len(listado),
                    )

                    if not listado:
                        # Sin más páginas
                        break

                    # Agrupar por organismo para hacer el FK guard antes del upsert
                    por_organismo: dict[int, list[dict[str, Any]]] = {}
                    for item in listado:
                        try:
                            codigo = int(item.get("CodigoOrganismo") or 0)
                        except (ValueError, TypeError):
                            continue
                        if codigo == 0:
                            continue
                        por_organismo.setdefault(codigo, []).append(item)

                    async with AsyncSessionLocal() as session:
                        for codigo_organismo, items_org in por_organismo.items():
                            # Garantizar que el organismo exista (FK guard)
                            await _upsert_organismo_si_falta(session, codigo_organismo)
                            cantidad = await _upsert_lineas(
                                session=session,
                                lineas=items_org,
                                codigo_organismo=codigo_organismo,
                                ano=ano,
                            )
                            stats["upserted"] += cantidad

                        await session.commit()

                    # Sin más páginas cuando la respuesta es menor que el tamaño máximo
                    if len(listado) < _PAGE_SIZE:
                        break

                    pagina += 1
                    # Rate limit: ~5 req/s entre páginas
                    await asyncio.sleep(_SLEEP_ENTRE_PAGINAS)

    finally:
        # Limpiar referencia al ticket en texto claro — regla de oro #2
        del ticket_plaintext

    return stats


async def _run(ano: int | None) -> dict[str, object]:
    """Lógica async principal de la tarea.

    Itera sobre todos los tickets activos y sincroniza el plan anual
    para cada empresa. El año actual y el siguiente se sincronizan
    por defecto (el PAC puede publicarse con anticipación).
    """
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal, engine
    from app.models.ticket import TicketApi

    # Disponer conexiones del pool heredadas del event loop anterior.
    # Cada task Celery corre en su propio asyncio.run() → nuevo event loop.
    await engine.dispose()

    # Determinar años a sincronizar
    ano_actual = datetime.now(UTC).year
    anos: list[int] = [ano] if ano is not None else [ano_actual, ano_actual + 1]

    logger.info("sync_plan_anual_start", anos=anos)

    # Obtener todos los tickets activos
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                TicketApi.empresa_id,
                TicketApi.ticket_cifrado,
                TicketApi.id,
            ).where(TicketApi.status == TicketStatus.active)
        )
        tickets = result.all()

    if not tickets:
        logger.info("sync_plan_anual_no_tickets")
        return {"empresas": 0, "total": {}}

    total: dict[str, int] = {"upserted": 0, "paginas": 0, "errores": 0}

    for empresa_id, ticket_cifrado, ticket_id in tickets:
        stats = await _sync_plan_empresa(
            empresa_id=str(empresa_id),
            ticket_cifrado=ticket_cifrado,
            ticket_id=str(ticket_id),
            anos=anos,
        )
        for k, v in stats.items():
            total[k] = total.get(k, 0) + v

    logger.info(
        "sync_plan_anual_done",
        empresas=len(tickets),
        anos=anos,
        **total,
    )
    return {"empresas": len(tickets), "anos": anos, "total": total}


@celery_app.task(  # type: ignore[misc]
    name="tasks.sync_plan_anual.sync_plan_anual",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutos entre reintentos
    acks_late=True,
)
def sync_plan_anual(self: Any, ano: int | None = None) -> dict[str, object]:
    """Sincroniza el Plan Anual de Compras desde la API de ChileCompra.

    Itera sobre todas las empresas con ticket activo y actualiza la tabla
    plan_anual_lineas con upsert idempotente.

    Regla de oro #29: idempotente — re-ejecutar no duplica registros.
    Regla de oro #2:  ticket descifrado solo en memoria.
    Regla de oro #18: rate limit activo (5 req/s con sleep entre páginas).

    Args:
        ano: Año a sincronizar. Si None, sincroniza año actual y siguiente.

    Returns:
        Dict con resumen: empresas procesadas, años y contadores totales.
    """
    logger.info("sync_plan_anual_task_start", ano=ano)
    return asyncio.run(_run(ano=ano))
