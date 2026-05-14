"""Tests unitarios para los endpoints del pipeline.

Cubre:
  GET    /api/v1/pipeline
  GET    /api/v1/pipeline/{id}
  PATCH  /api/v1/pipeline/{id}
  POST   /api/v1/pipeline/{id}/notas
  DELETE /api/v1/pipeline/{id}/notas/{nota_id}

Usa BD de test real con AsyncClient + ASGITransport.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from httpx import AsyncClient  # noqa: TCH002
import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.security import create_access_token
from app.models.empresa import Empresa
from app.models.enums import LicitacionEstado, UserRole, UserStatus
from app.models.licitacion import Licitacion
from app.models.pipeline import PipelineItem, PipelineNota

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession


def _auth_headers(user_id: str) -> dict[str, str]:
    token = create_access_token(subject=user_id)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def limpiar_pipeline(db_session: AsyncSession) -> None:
    await db_session.execute(delete(PipelineNota))
    await db_session.execute(delete(PipelineItem))
    await db_session.commit()


@pytest_asyncio.fixture
async def empresa_con_usuario(
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> tuple[Any, Empresa]:
    user: Any = await make_user(
        email="pipeline_test@example.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        razon_social="Pipeline Test SpA",
    )
    result = await db_session.execute(
        select(Empresa).where(Empresa.usuario_id == user.id)
    )
    empresa: Empresa = result.scalar_one()
    return user, empresa


@pytest_asyncio.fixture
async def segunda_empresa(
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> tuple[Any, Empresa]:
    user: Any = await make_user(
        email="pipeline_otra@example.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        razon_social="Otra Empresa SpA",
    )
    result = await db_session.execute(
        select(Empresa).where(Empresa.usuario_id == user.id)
    )
    empresa: Empresa = result.scalar_one()
    return user, empresa


@pytest_asyncio.fixture
async def licitacion_basica(db_session: AsyncSession) -> Licitacion:
    """Crea una licitación mínima para usar en tests de pipeline."""
    await db_session.execute(
        pg_insert(Licitacion)
        .values(
            codigo="TEST-PIPE-001",
            nombre="Licitación de prueba pipeline",
            estado=LicitacionEstado.publicada,
            moneda="CLP",
        )
        .on_conflict_do_nothing(index_elements=["codigo"])
    )
    await db_session.commit()
    result = await db_session.execute(
        select(Licitacion).where(Licitacion.codigo == "TEST-PIPE-001")
    )
    return result.scalar_one()


@pytest_asyncio.fixture
async def pipeline_item(
    empresa_con_usuario: tuple[Any, Empresa],
    licitacion_basica: Licitacion,
    db_session: AsyncSession,
) -> PipelineItem:
    _, empresa = empresa_con_usuario
    item = PipelineItem(
        empresa_id=empresa.id,
        licitacion_codigo=licitacion_basica.codigo,
        score=72,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item


# ---------------------------------------------------------------------------
# GET /pipeline — listado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_pipeline_vacio(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
) -> None:
    user, _ = empresa_con_usuario
    resp = await client.get("/api/v1/pipeline", headers=_auth_headers(str(user.id)))
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_listar_pipeline_sin_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/pipeline")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_listar_pipeline_con_item(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    pipeline_item: PipelineItem,
) -> None:
    user, _ = empresa_con_usuario
    resp = await client.get("/api/v1/pipeline", headers=_auth_headers(str(user.id)))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["estado"] == "nueva"
    assert item["score"] == 72
    assert item["licitacion"]["codigo"] == "TEST-PIPE-001"
    assert item["notas_count"] == 0


@pytest.mark.asyncio
async def test_listar_pipeline_filtro_estado(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    pipeline_item: PipelineItem,
) -> None:
    user, _ = empresa_con_usuario
    # Filtro que no coincide
    resp = await client.get(
        "/api/v1/pipeline?estado=adjudicada",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    # Filtro que sí coincide
    resp2 = await client.get(
        "/api/v1/pipeline?estado=nueva",
        headers=_auth_headers(str(user.id)),
    )
    assert resp2.status_code == 200
    assert resp2.json()["total"] == 1


@pytest.mark.asyncio
async def test_listar_pipeline_filtro_score_min(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    pipeline_item: PipelineItem,
) -> None:
    user, _ = empresa_con_usuario
    # score=72 → score_min=80 no debe aparecer
    resp = await client.get(
        "/api/v1/pipeline?score_min=80",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.json()["total"] == 0

    # score_min=70 sí debe aparecer
    resp2 = await client.get(
        "/api/v1/pipeline?score_min=70",
        headers=_auth_headers(str(user.id)),
    )
    assert resp2.json()["total"] == 1


@pytest.mark.asyncio
async def test_listar_pipeline_paginacion(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    pipeline_item: PipelineItem,
    db_session: AsyncSession,
) -> None:
    _, empresa = empresa_con_usuario
    user, _ = empresa_con_usuario

    # Insertar segunda licitación y segundo pipeline item
    await db_session.execute(
        pg_insert(Licitacion)
        .values(
            codigo="TEST-PIPE-002",
            nombre="Licitación de prueba 2",
            estado=LicitacionEstado.publicada,
            moneda="CLP",
        )
        .on_conflict_do_nothing(index_elements=["codigo"])
    )
    item2 = PipelineItem(
        empresa_id=empresa.id,
        licitacion_codigo="TEST-PIPE-002",
        score=80,
    )
    db_session.add(item2)
    await db_session.commit()

    resp = await client.get(
        "/api/v1/pipeline?page=1&page_size=1",
        headers=_auth_headers(str(user.id)),
    )
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1
    # El de score más alto va primero
    assert data["items"][0]["score"] == 80


# ---------------------------------------------------------------------------
# GET /pipeline/{id} — detalle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_obtener_item_ok(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    pipeline_item: PipelineItem,
) -> None:
    user, _ = empresa_con_usuario
    resp = await client.get(
        f"/api/v1/pipeline/{pipeline_item.id}",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(pipeline_item.id)
    assert "notas" in data


@pytest.mark.asyncio
async def test_obtener_item_no_existente(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
) -> None:
    import uuid

    user, _ = empresa_con_usuario
    resp = await client.get(
        f"/api/v1/pipeline/{uuid.uuid4()}",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_obtener_item_ajeno_retorna_403(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    segunda_empresa: tuple[Any, Any],
    pipeline_item: PipelineItem,
) -> None:
    user_b, _ = segunda_empresa
    resp = await client.get(
        f"/api/v1/pipeline/{pipeline_item.id}",
        headers=_auth_headers(str(user_b.id)),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /pipeline/{id} — actualización
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_estado(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    pipeline_item: PipelineItem,
) -> None:
    user, _ = empresa_con_usuario
    resp = await client.patch(
        f"/api/v1/pipeline/{pipeline_item.id}",
        json={"estado": "interesado"},
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    assert resp.json()["estado"] == "interesado"


@pytest.mark.asyncio
async def test_patch_razon_descarte(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    pipeline_item: PipelineItem,
) -> None:
    user, _ = empresa_con_usuario
    resp = await client.patch(
        f"/api/v1/pipeline/{pipeline_item.id}",
        json={"estado": "descartada", "razon_descarte": "Fuera de nuestro rubro"},
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["estado"] == "descartada"
    assert data["razon_descarte"] == "Fuera de nuestro rubro"


@pytest.mark.asyncio
async def test_patch_estado_invalido(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    pipeline_item: PipelineItem,
) -> None:
    user, _ = empresa_con_usuario
    resp = await client.patch(
        f"/api/v1/pipeline/{pipeline_item.id}",
        json={"estado": "inexistente"},
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /pipeline/{id}/notas — crear nota
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crear_nota_ok(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    pipeline_item: PipelineItem,
) -> None:
    user, _ = empresa_con_usuario
    resp = await client.post(
        f"/api/v1/pipeline/{pipeline_item.id}/notas",
        json={"contenido": "Hay que revisar las bases técnicas"},
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["contenido"] == "Hay que revisar las bases técnicas"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_crear_nota_contenido_vacio_retorna_422(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    pipeline_item: PipelineItem,
) -> None:
    user, _ = empresa_con_usuario
    resp = await client.post(
        f"/api/v1/pipeline/{pipeline_item.id}/notas",
        json={"contenido": ""},
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_crear_nota_item_ajeno_retorna_403(
    client: AsyncClient,
    segunda_empresa: tuple[Any, Any],
    pipeline_item: PipelineItem,
) -> None:
    user_b, _ = segunda_empresa
    resp = await client.post(
        f"/api/v1/pipeline/{pipeline_item.id}/notas",
        json={"contenido": "No debería poder"},
        headers=_auth_headers(str(user_b.id)),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_notas_aparecen_en_detalle(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    pipeline_item: PipelineItem,
) -> None:
    user, _ = empresa_con_usuario
    headers = _auth_headers(str(user.id))

    # Crear dos notas
    await client.post(
        f"/api/v1/pipeline/{pipeline_item.id}/notas",
        json={"contenido": "Primera nota"},
        headers=headers,
    )
    await client.post(
        f"/api/v1/pipeline/{pipeline_item.id}/notas",
        json={"contenido": "Segunda nota"},
        headers=headers,
    )

    # El detalle debe incluirlas
    resp = await client.get(
        f"/api/v1/pipeline/{pipeline_item.id}",
        headers=headers,
    )
    data = resp.json()
    assert data["notas_count"] == 2
    assert len(data["notas"]) == 2


# ---------------------------------------------------------------------------
# DELETE /pipeline/{id}/notas/{nota_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eliminar_nota_ok(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    pipeline_item: PipelineItem,
    db_session: AsyncSession,
) -> None:
    user, _ = empresa_con_usuario
    headers = _auth_headers(str(user.id))

    # Crear nota
    resp = await client.post(
        f"/api/v1/pipeline/{pipeline_item.id}/notas",
        json={"contenido": "A eliminar"},
        headers=headers,
    )
    nota_id = resp.json()["id"]

    # Eliminar
    resp_del = await client.delete(
        f"/api/v1/pipeline/{pipeline_item.id}/notas/{nota_id}",
        headers=headers,
    )
    assert resp_del.status_code == 204

    # Verificar que no existe
    import uuid

    check = await db_session.execute(
        select(PipelineNota).where(PipelineNota.id == uuid.UUID(nota_id))
    )
    assert check.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_eliminar_nota_ajena_retorna_403(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    segunda_empresa: tuple[Any, Any],
    pipeline_item: PipelineItem,
) -> None:
    user_a, _ = empresa_con_usuario
    user_b, _ = segunda_empresa

    # Usuario A crea nota
    resp = await client.post(
        f"/api/v1/pipeline/{pipeline_item.id}/notas",
        json={"contenido": "Nota de A"},
        headers=_auth_headers(str(user_a.id)),
    )
    nota_id = resp.json()["id"]

    # Usuario B intenta borrarla (pero ni siquiera puede ver el item)
    resp_del = await client.delete(
        f"/api/v1/pipeline/{pipeline_item.id}/notas/{nota_id}",
        headers=_auth_headers(str(user_b.id)),
    )
    assert resp_del.status_code == 403
