"""Tests unitarios para MercadoPublicoClient con mocks via respx.

Casos cubiertos:
- Happy path: listado y detalle.
- 429 → RateLimitError.
- 5xx → MercadoPublicoError.
- Timeout → MPTimeoutError.
- 401 → TicketInvalidoError.
- 404 (lista vacía) → LicitacionNoEncontradaError.
"""

from collections.abc import Generator
from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from app.services.chilecompra.client import MercadoPublicoClient
from app.services.chilecompra.enums import EstadoLicitacion
from app.services.chilecompra.exceptions import (
    LicitacionNoEncontradaError,
    MercadoPublicoError,
    RateLimitError,
    TicketInvalidoError,
)
from app.services.chilecompra.exceptions import TimeoutError as MPTimeoutError

TICKET = "F8537A18-6766-4DEF-9E59-426B4FEE2844"
BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico"

LISTADO_RESPONSE = {
    "Cantidad": 2,
    "FechaCreacion": "2026-05-09T19:56:10.7712778Z",
    "Version": "v1",
    "Listado": [
        {
            "CodigoExterno": "1000-8-LE26",
            "Nombre": "Sum. material pétreo",
            "CodigoEstado": 5,
            "FechaCierre": "2026-05-18T15:10:00",
        },
        {
            "CodigoExterno": "1001-7-LP26",
            "Nombre": "SUMINISTRO DE SAL",
            "CodigoEstado": 5,
            "FechaCierre": "2026-05-14T15:00:00",
        },
    ],
}

DETALLE_RESPONSE = {
    "Cantidad": 1,
    "FechaCreacion": "2026-05-09T19:56:19Z",
    "Version": "v1",
    "Listado": [
        {
            "CodigoExterno": "1000-8-LE26",
            "Nombre": "Sum. material pétreo",
            "CodigoEstado": 5,
            "Estado": "Publicada",
            "Descripcion": "Para obras de recebo...",
            "FechaCierre": "2026-05-18T15:10:00",
            "Comprador": {
                "CodigoOrganismo": "7248",
                "NombreOrganismo": "MOP",
                "RutUnidad": "61.202.000-0",
            },
            "Moneda": "CLP",
            "MontoEstimado": None,
            "EsRenovable": 0,
            "Fechas": {
                "FechaCreacion": "2026-04-28T17:53:29.51",
                "FechaCierre": "2026-05-18T15:10:00",
                "FechaPublicacion": "2026-05-08T16:03:02.313",
            },
            "Items": {
                "Cantidad": 1,
                "Listado": [
                    {
                        "Correlativo": 1,
                        "CodigoProducto": 11111611,
                        "NombreProducto": "Grava",
                        "Cantidad": 1500.0,
                    }
                ],
            },
        }
    ],
}


@pytest.fixture
def mock_log() -> Generator[None, None, None]:
    """Mockea el logging a BD para tests unitarios."""
    with patch(
        "app.services.chilecompra.client.MercadoPublicoClient._log_request",
        new_callable=AsyncMock,
    ):
        yield


@pytest.mark.asyncio
class TestListarLicitaciones:
    """Tests del método listar_licitaciones_por_estado."""

    @respx.mock
    async def test_happy_path_activas(self, mock_log: None) -> None:
        respx.get(f"{BASE_URL}/licitaciones.json").mock(
            return_value=httpx.Response(200, json=LISTADO_RESPONSE)
        )
        async with MercadoPublicoClient() as client:
            response = await client.listar_licitaciones_por_estado(
                estado=EstadoLicitacion.ACTIVAS,
                ticket=TICKET,
            )
        assert response.Cantidad == 2
        assert len(response.Listado) == 2
        assert response.Listado[0].CodigoExterno == "1000-8-LE26"

    @respx.mock
    async def test_429_lanza_rate_limit_error(self, mock_log: None) -> None:
        respx.get(f"{BASE_URL}/licitaciones.json").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "60"})
        )
        async with MercadoPublicoClient() as client:
            with pytest.raises(RateLimitError):
                await client.listar_licitaciones_por_estado(
                    estado=EstadoLicitacion.ACTIVAS,
                    ticket=TICKET,
                )

    @respx.mock
    async def test_5xx_lanza_mercado_publico_error(self, mock_log: None) -> None:
        respx.get(f"{BASE_URL}/licitaciones.json").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )
        async with MercadoPublicoClient() as client:
            with pytest.raises(MercadoPublicoError) as exc_info:
                await client.listar_licitaciones_por_estado(
                    estado=EstadoLicitacion.ACTIVAS,
                    ticket=TICKET,
                )
        assert exc_info.value.status_code == 503

    @respx.mock
    async def test_401_lanza_ticket_invalido(self, mock_log: None) -> None:
        respx.get(f"{BASE_URL}/licitaciones.json").mock(
            return_value=httpx.Response(401)
        )
        async with MercadoPublicoClient() as client:
            with pytest.raises(TicketInvalidoError):
                await client.listar_licitaciones_por_estado(
                    estado=EstadoLicitacion.ACTIVAS,
                    ticket=TICKET,
                )

    @respx.mock
    async def test_timeout_lanza_mp_timeout_error(self, mock_log: None) -> None:
        respx.get(f"{BASE_URL}/licitaciones.json").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        async with MercadoPublicoClient() as client:
            with pytest.raises(MPTimeoutError):
                await client.listar_licitaciones_por_estado(
                    estado=EstadoLicitacion.ACTIVAS,
                    ticket=TICKET,
                )


@pytest.mark.asyncio
class TestObtenerDetalle:
    """Tests del método obtener_detalle_licitacion."""

    @respx.mock
    async def test_happy_path_detalle(self, mock_log: None) -> None:
        respx.get(f"{BASE_URL}/licitaciones.json").mock(
            return_value=httpx.Response(200, json=DETALLE_RESPONSE)
        )
        async with MercadoPublicoClient() as client:
            response = await client.obtener_detalle_licitacion(
                codigo="1000-8-LE26",
                ticket=TICKET,
            )
        assert response.Cantidad == 1
        licitacion = response.Listado[0]
        assert licitacion.CodigoExterno == "1000-8-LE26"
        assert licitacion.Comprador is not None
        assert licitacion.Comprador.CodigoOrganismo == "7248"
        assert licitacion.Items is not None
        assert licitacion.Items.Cantidad == 1

    @respx.mock
    async def test_lista_vacia_lanza_no_encontrada(self, mock_log: None) -> None:
        respx.get(f"{BASE_URL}/licitaciones.json").mock(
            return_value=httpx.Response(
                200,
                json={"Cantidad": 0, "Listado": []},
            )
        )
        async with MercadoPublicoClient() as client:
            with pytest.raises(LicitacionNoEncontradaError):
                await client.obtener_detalle_licitacion(
                    codigo="9999-99-XX99",
                    ticket=TICKET,
                )


@pytest.mark.asyncio
class TestListarPorFecha:
    """Tests del método listar_licitaciones_por_fecha."""

    @respx.mock
    async def test_formato_fecha_en_params(self, mock_log: None) -> None:
        """Verifica que la fecha se envía en formato ddmmaaaa."""
        route = respx.get(f"{BASE_URL}/licitaciones.json").mock(
            return_value=httpx.Response(200, json=LISTADO_RESPONSE)
        )
        async with MercadoPublicoClient() as client:
            await client.listar_licitaciones_por_fecha(
                fecha=date(2026, 5, 7),
                ticket=TICKET,
            )
        # Verificar que el param fecha fue "07052026"
        assert route.called
        request = route.calls[0].request
        assert "fecha=07052026" in str(request.url)
