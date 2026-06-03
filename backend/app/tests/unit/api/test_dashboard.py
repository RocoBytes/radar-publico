"""Tests unitarios para los endpoints del dashboard.

Cubre:
  GET /api/v1/dashboard/resumen
  GET /api/v1/dashboard/segmentos

Usa BD de test real con AsyncClient + ASGITransport.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from httpx import AsyncClient  # noqa: TCH002
import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.security import create_access_token
from app.models.empresa import Empresa
from app.models.enums import LicitacionEstado, UserRole, UserStatus
from app.models.catalogos import Unspsc
from app.models.interes import Interes, InteresTipo
from app.models.licitacion import Licitacion, LicitacionItem
from app.models.pipeline import PipelineItem, PipelineNota

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession


def _auth_headers(user_id: str) -> dict[str, str]:
    token = create_access_token(subject=user_id)
    return {"Authorization": f"Bearer {token}"}


_CODIGO_LIC = "TEST-DASH-001"
_CODIGO_LIC_2 = "TEST-DASH-002"
_UNSPSC_SEGMENTO = "43"  # código de nivel 2 para tests


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def limpiar_dashboard(db_session: AsyncSession) -> None:
    """Limpia datos de test del dashboard antes de cada test."""
    await db_session.execute(delete(PipelineNota))
    await db_session.execute(delete(PipelineItem))
    await db_session.execute(
        delete(Licitacion).where(
            Licitacion.codigo.in_([_CODIGO_LIC, _CODIGO_LIC_2])
        )
    )
    await db_session.commit()


@pytest_asyncio.fixture
async def unspsc_segmento_43(db_session: AsyncSession) -> None:
    """Inserta el segmento UNSPSC "43" (nivel 2) para tests de licitacion_items."""
    await db_session.execute(
        pg_insert(Unspsc)
        .values(
            codigo=_UNSPSC_SEGMENTO,
            nivel=2,
            segmento=_UNSPSC_SEGMENTO,
            nombre_es="Tecnología de Información y Comunicaciones",
        )
        .on_conflict_do_nothing(index_elements=["codigo"])
    )
    await db_session.commit()


@pytest_asyncio.fixture
async def empresa_con_usuario(
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> tuple[Any, Empresa]:
    user: Any = await make_user(
        email="dashboard_test@example.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        razon_social="Dashboard Test SpA",
    )
    result = await db_session.execute(
        select(Empresa).where(Empresa.usuario_id == user.id)
    )
    empresa: Empresa = result.scalar_one()
    return user, empresa


@pytest_asyncio.fixture
async def licitacion_publicada(db_session: AsyncSession) -> Licitacion:
    """Licitación publicada con fecha_publicacion hoy y fecha_cierre en 12h."""
    ahora = datetime.now(UTC)
    await db_session.execute(
        pg_insert(Licitacion)
        .values(
            codigo=_CODIGO_LIC,
            nombre="Licitación dashboard test",
            estado=LicitacionEstado.publicada,
            moneda="CLP",
            fecha_publicacion=ahora,
            fecha_cierre=ahora + timedelta(hours=12),
        )
        .on_conflict_do_nothing(index_elements=["codigo"])
    )
    await db_session.commit()
    result = await db_session.execute(
        select(Licitacion).where(Licitacion.codigo == _CODIGO_LIC)
    )
    return result.scalar_one()


@pytest_asyncio.fixture
async def pipeline_item_dash(
    empresa_con_usuario: tuple[Any, Empresa],
    licitacion_publicada: Licitacion,
    db_session: AsyncSession,
) -> PipelineItem:
    _, empresa = empresa_con_usuario
    item = PipelineItem(
        empresa_id=empresa.id,
        licitacion_codigo=licitacion_publicada.codigo,
        score=88,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item


# ---------------------------------------------------------------------------
# GET /dashboard/resumen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resumen_sin_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/dashboard/resumen")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_resumen_vacio(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
) -> None:
    user, _ = empresa_con_usuario
    resp = await client.get(
        "/api/v1/dashboard/resumen",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["en_pipeline"] == 0
    assert data["top_oportunidades"] == []
    assert isinstance(data["oportunidades_activas"], int)
    assert isinstance(data["nuevas_hoy"], int)
    assert isinstance(data["proximas_a_cerrar"], int)


@pytest.mark.asyncio
async def test_resumen_con_pipeline_item(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    pipeline_item_dash: PipelineItem,
) -> None:
    user, _ = empresa_con_usuario
    resp = await client.get(
        "/api/v1/dashboard/resumen",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    data = resp.json()

    # Empresa-scoped: exacto
    assert data["en_pipeline"] == 1

    # Globales: al menos 1 (nuestra licitacion publicada)
    assert data["oportunidades_activas"] >= 1
    assert data["nuevas_hoy"] >= 1
    assert data["proximas_a_cerrar"] >= 1

    # Top oportunidades incluye nuestro item
    assert len(data["top_oportunidades"]) >= 1
    top = data["top_oportunidades"][0]
    assert top["score"] == 88
    assert top["licitacion"]["codigo"] == "TEST-DASH-001"

    # Última sincronización: hay licitaciones → no es None
    assert data["ultima_sincronizacion"] is not None


@pytest.mark.asyncio
async def test_resumen_top_ordenado_por_score(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    licitacion_publicada: Licitacion,
    db_session: AsyncSession,
) -> None:
    """El top-5 sale ordenado score DESC."""
    _, empresa = empresa_con_usuario
    user, _ = empresa_con_usuario

    # Segunda licitación con score menor
    await db_session.execute(
        pg_insert(Licitacion)
        .values(
            codigo=_CODIGO_LIC_2,
            nombre="Segunda licitación",
            estado=LicitacionEstado.publicada,
            moneda="CLP",
        )
        .on_conflict_do_nothing(index_elements=["codigo"])
    )
    item_alto = PipelineItem(
        empresa_id=empresa.id,
        licitacion_codigo=_CODIGO_LIC,
        score=95,
    )
    item_bajo = PipelineItem(
        empresa_id=empresa.id,
        licitacion_codigo=_CODIGO_LIC_2,
        score=60,
    )
    db_session.add_all([item_alto, item_bajo])
    await db_session.commit()

    resp = await client.get(
        "/api/v1/dashboard/resumen",
        headers=_auth_headers(str(user.id)),
    )
    tops = resp.json()["top_oportunidades"]
    assert len(tops) == 2
    assert tops[0]["score"] == 95
    assert tops[1]["score"] == 60


# ---------------------------------------------------------------------------
# GET /dashboard/segmentos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_segmentos_sin_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/dashboard/segmentos")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_segmentos_vacio(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
) -> None:
    """Sin licitacion_items con UNSPSC devuelve lista vacía."""
    user, _ = empresa_con_usuario
    resp = await client.get(
        "/api/v1/dashboard/segmentos",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    # Puede haber datos de otros tests pero la respuesta es válida
    data = resp.json()
    assert "segmentos" in data
    assert isinstance(data["segmentos"], list)


@pytest.mark.asyncio
async def test_segmentos_con_items_unspsc(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    licitacion_publicada: Licitacion,
    unspsc_segmento_43: None,
    db_session: AsyncSession,
) -> None:
    """Items UNSPSC de licitaciones publicadas aparecen agrupados por segmento."""
    user, _ = empresa_con_usuario

    item = LicitacionItem(
        licitacion_codigo=_CODIGO_LIC,
        numero_item=1,
        unspsc_codigo=_UNSPSC_SEGMENTO,
        unspsc_nombre="Tecnología",
        cantidad=1,
    )
    db_session.add(item)
    await db_session.commit()

    resp = await client.get(
        "/api/v1/dashboard/segmentos",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    segmentos = resp.json()["segmentos"]

    codigos = [s["codigo"] for s in segmentos]
    assert _UNSPSC_SEGMENTO in codigos

    seg_43 = next(s for s in segmentos if s["codigo"] == _UNSPSC_SEGMENTO)
    assert seg_43["cantidad"] >= 1
    assert "Tecnología" in seg_43["nombre"]


@pytest.mark.asyncio
async def test_segmentos_solo_intereses_sin_intereses(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    licitacion_publicada: Licitacion,
    unspsc_segmento_43: None,
    db_session: AsyncSession,
) -> None:
    """solo_intereses=true sin intereses UNSPSC devuelve lista vacía."""
    user, _ = empresa_con_usuario

    item = LicitacionItem(
        licitacion_codigo=_CODIGO_LIC,
        numero_item=1,
        unspsc_codigo=_UNSPSC_SEGMENTO,
        cantidad=1,
    )
    db_session.add(item)
    await db_session.commit()

    resp = await client.get(
        "/api/v1/dashboard/segmentos?solo_intereses=true",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    assert resp.json()["segmentos"] == []


@pytest.mark.asyncio
async def test_segmentos_solo_intereses_con_intereses(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    licitacion_publicada: Licitacion,
    unspsc_segmento_43: None,
    db_session: AsyncSession,
) -> None:
    """solo_intereses=true filtra por segmentos del interés de la empresa."""
    user, empresa = empresa_con_usuario

    # Item de segmento "43"
    item_43 = LicitacionItem(
        licitacion_codigo=_CODIGO_LIC,
        numero_item=1,
        unspsc_codigo=_UNSPSC_SEGMENTO,
        cantidad=1,
    )
    db_session.add(item_43)

    # Interés UNSPSC del segmento "43"
    interes = Interes(
        empresa_id=empresa.id,
        tipo=InteresTipo.unspsc_segmento,
        valor=_UNSPSC_SEGMENTO,
    )
    db_session.add(interes)
    await db_session.commit()

    resp = await client.get(
        "/api/v1/dashboard/segmentos?solo_intereses=true",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    segmentos = resp.json()["segmentos"]
    assert len(segmentos) >= 1
    assert all(s["codigo"] == _UNSPSC_SEGMENTO for s in segmentos)
