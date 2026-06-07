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
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.security import create_access_token
from app.models.catalogos import Unspsc
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
    """BD vacía → items=[], has_next=False."""
    user = await make_user()
    resp = await client.get(
        "/api/v1/licitaciones",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["has_next"] is False
    assert data["page"] == 1
    assert data["page_size"] == 25


@pytest.mark.asyncio
async def test_listado_con_licitaciones(
    client: AsyncClient,
    make_user: Any,
    db_session: AsyncSession,
) -> None:
    """3 licitaciones insertadas → 3 items, has_next=False (menos que page_size)."""
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
    assert len(data["items"]) == 3
    assert data["has_next"] is False
    assert data["page"] == 1
    assert data["page_size"] == 25


@pytest.mark.asyncio
async def test_listado_has_next_true(
    client: AsyncClient,
    make_user: Any,
    db_session: AsyncSession,
) -> None:
    """page_size+1 ítems disponibles → has_next=True, solo page_size devueltos."""
    user = await make_user()

    # Insertar page_size+1 = 3 licitaciones con page_size=2
    lics = [_licitacion(f"HASNEXT-{i:04d}-L123") for i in range(3)]
    db_session.add_all(lics)
    await db_session.commit()

    resp = await client.get(
        "/api/v1/licitaciones",
        params={"page": 1, "page_size": 2},
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["has_next"] is True

    # Página 2 tiene el tercer ítem y has_next=False
    resp2 = await client.get(
        "/api/v1/licitaciones",
        params={"page": 2, "page_size": 2},
        headers=_auth_headers(str(user.id)),
    )
    data2 = resp2.json()
    assert len(data2["items"]) == 1
    assert data2["has_next"] is False


@pytest.mark.asyncio
async def test_filtro_por_estado(
    client: AsyncClient,
    make_user: Any,
    db_session: AsyncSession,
) -> None:
    """2 publicadas + 1 cerrada: filtrar estado=publicada → 2 items, has_next=False."""
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
    assert len(data["items"]) == 2
    assert data["has_next"] is False
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


@pytest.mark.asyncio
async def test_filtro_por_unspsc(
    client: AsyncClient,
    make_user: Any,
    db_session: AsyncSession,
) -> None:
    """Filtro UNSPSC con jerarquía:

    - lic_A tiene item con unspsc_codigo=73101500 (segmento 73)
    - lic_B tiene item con unspsc_codigo=80101500 (segmento 80)
    - unspsc_codigo=73    → solo lic_A
    - unspsc_codigo=8010  → solo lic_B
    - unspsc_codigo=99    → 0 resultados
    """
    user = await make_user()

    # Insertar códigos UNSPSC mínimos para satisfacer la FK de licitacion_items.
    # ON CONFLICT DO NOTHING garantiza idempotencia entre runs consecutivos.
    await db_session.execute(
        pg_insert(Unspsc)
        .values(
            [
                {
                    "codigo": "73101500",
                    "nombre_es": "Limpieza general",
                    "nivel": 8,
                    "segmento": "73",
                    "familia": "7310",
                    "clase": "731015",
                    "commodity": "73101500",
                },
                {
                    "codigo": "80101500",
                    "nombre_es": "Auditoría contable",
                    "nivel": 8,
                    "segmento": "80",
                    "familia": "8010",
                    "clase": "801015",
                    "commodity": "80101500",
                },
            ]
        )
        .on_conflict_do_nothing(index_elements=["codigo"])
    )
    await db_session.flush()

    lic_a = _licitacion("UNSPSC-A-L123")
    lic_b = _licitacion("UNSPSC-B-L123")
    db_session.add_all([lic_a, lic_b])
    await db_session.flush()

    item_a = LicitacionItem(
        licitacion_codigo="UNSPSC-A-L123",
        numero_item=1,
        unspsc_codigo="73101500",
        nombre_producto="Servicio de limpieza",
    )
    item_b = LicitacionItem(
        licitacion_codigo="UNSPSC-B-L123",
        numero_item=1,
        unspsc_codigo="80101500",
        nombre_producto="Servicio de auditoría",
    )
    db_session.add_all([item_a, item_b])
    await db_session.commit()

    headers = _auth_headers(str(user.id))

    # Segmento 73 → solo lic_A
    resp = await client.get(
        "/api/v1/licitaciones",
        params={"unspsc_codigo": "73"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["has_next"] is False
    assert data["items"][0]["codigo"] == "UNSPSC-A-L123"

    # Familia 8010 → solo lic_B
    resp = await client.get(
        "/api/v1/licitaciones",
        params={"unspsc_codigo": "8010"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["has_next"] is False
    assert data["items"][0]["codigo"] == "UNSPSC-B-L123"

    # Segmento 99 → ninguna
    resp = await client.get(
        "/api/v1/licitaciones",
        params={"unspsc_codigo": "99"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["has_next"] is False
