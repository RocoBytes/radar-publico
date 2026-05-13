"""Tests unitarios para los endpoints GET /api/v1/licitaciones.

Usa BD de test real (NullPool via conftest) con AsyncClient + ASGITransport.
Los tokens JWT se generan directamente desde app.core.security para evitar
el round-trip HTTP de /login.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from httpx import AsyncClient  # noqa: TCH002
import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.core.security import create_access_token
from app.models.enums import FechaTipo, LicitacionEstado
from app.models.licitacion import (
    Licitacion,
    LicitacionFecha,
    LicitacionItem,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_headers(user_id: str) -> dict[str, str]:
    """Genera cabecera Authorization con JWT válido para el user_id dado."""
    token = create_access_token(subject=user_id)
    return {"Authorization": f"Bearer {token}"}


def _licitacion(
    codigo: str,
    estado: LicitacionEstado = LicitacionEstado.publicada,
    *,
    nombre: str | None = None,
) -> Licitacion:
    """Factoría de objetos Licitacion para tests."""
    return Licitacion(
        codigo=codigo,
        nombre=nombre or f"Licitación de prueba {codigo}",
        estado=estado,
        moneda="CLP",
        es_renovable=False,
        fecha_publicacion=datetime(2026, 5, 1, tzinfo=UTC),
        fecha_cierre=datetime(2026, 6, 1, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Fixtures de limpieza
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def limpiar_licitaciones(db_session: AsyncSession) -> None:
    """Elimina todas las licitaciones antes de cada test para aislar el estado."""
    await db_session.execute(delete(Licitacion))
    await db_session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listado_sin_autenticacion(client: AsyncClient) -> None:
    """Sin JWT → 401 Unauthorized."""
    resp = await client.get("/api/v1/licitaciones")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_listado_vacio(
    client: AsyncClient,
    make_user: Any,
) -> None:
    """BD vacía → items=[], total=0."""
    user = await make_user()
    resp = await client.get(
        "/api/v1/licitaciones",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 25


@pytest.mark.asyncio
async def test_listado_con_licitaciones(
    client: AsyncClient,
    make_user: Any,
    db_session: AsyncSession,
) -> None:
    """3 licitaciones insertadas → total=3, paginación coherente."""
    user = await make_user()

    lics = [_licitacion(f"TEST-{i:04d}-L123") for i in range(3)]
    db_session.add_all(lics)
    await db_session.commit()

    resp = await client.get(
        "/api/v1/licitaciones",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["page"] == 1
    assert data["page_size"] == 25


@pytest.mark.asyncio
async def test_filtro_por_estado(
    client: AsyncClient,
    make_user: Any,
    db_session: AsyncSession,
) -> None:
    """2 publicadas + 1 cerrada: filtrar estado=publicada → total=2."""
    user = await make_user()

    lics = [
        _licitacion("FILT-0001-L123", LicitacionEstado.publicada),
        _licitacion("FILT-0002-L123", LicitacionEstado.publicada),
        _licitacion("FILT-0003-L123", LicitacionEstado.cerrada),
    ]
    db_session.add_all(lics)
    await db_session.commit()

    resp = await client.get(
        "/api/v1/licitaciones",
        params={"estado": "publicada"},
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert all(item["estado"] == "publicada" for item in data["items"])


@pytest.mark.asyncio
async def test_detalle_ok(
    client: AsyncClient,
    make_user: Any,
    db_session: AsyncSession,
) -> None:
    """Licitación con 1 item + 1 fecha: detalle retorna todos los campos."""
    user = await make_user()
    codigo = "DET-0001-L123"

    lic = _licitacion(codigo)
    lic.descripcion = "Descripción de prueba"
    lic.contacto_nombre = "Juan Pérez"
    lic.contacto_email = "juan@organismo.cl"
    db_session.add(lic)
    await db_session.flush()

    item = LicitacionItem(
        licitacion_codigo=codigo,
        numero_item=1,
        nombre_producto="Papel A4",
        cantidad=10.0,
        unidad="resma",
        monto_unitario_estimado=5000.0,
    )
    fecha = LicitacionFecha(
        licitacion_codigo=codigo,
        tipo=FechaTipo.cierre,
        fecha=datetime(2026, 6, 1, tzinfo=UTC),
        es_estimada=False,
    )
    db_session.add(item)
    db_session.add(fecha)
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/licitaciones/{codigo}",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["codigo"] == codigo
    assert data["descripcion"] == "Descripción de prueba"
    assert data["contacto_nombre"] == "Juan Pérez"
    assert data["contacto_email"] == "juan@organismo.cl"
    assert len(data["items"]) == 1
    assert data["items"][0]["nombre_producto"] == "Papel A4"
    assert len(data["fechas"]) == 1
    assert data["fechas"][0]["tipo"] == "cierre"


@pytest.mark.asyncio
async def test_detalle_no_encontrado(
    client: AsyncClient,
    make_user: Any,
) -> None:
    """Código inexistente → 404 Not Found."""
    user = await make_user()
    resp = await client.get(
        "/api/v1/licitaciones/NOEXISTE-9999-L123",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 404
