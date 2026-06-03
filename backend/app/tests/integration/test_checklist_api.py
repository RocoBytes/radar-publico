"""Tests de integración para los endpoints del checklist documental.

Requiere Postgres corriendo con schema y migraciones aplicadas.
Marcados como @pytest.mark.integration.

Tests:
- test_crud_checklist_completo: crear, listar, actualizar (completar), eliminar
- test_acceso_no_autorizado_checklist: empresa B no puede leer/modificar checklist de empresa A
- test_cascade_delete_pipeline_item: eliminar pipeline_item borra sus checklist_items
"""

from collections.abc import AsyncGenerator, Callable
from typing import Any
import uuid

from httpx import AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.models.enums import LicitacionEstado, UserRole, UserStatus
from app.models.licitacion import Licitacion
from app.models.pipeline import PipelineChecklistItem, PipelineItem

pytestmark = pytest.mark.integration

UserFactory = Callable[..., Any]

# Código de licitación de prueba usado en todos los tests
_CODIGO_LIC = f"TEST-CL-{uuid.uuid4().hex[:6].upper()}"


async def _get_auth_header(
    client: AsyncClient, email: str, password: str
) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login falló: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture(scope="function")
async def licitacion_prueba() -> AsyncGenerator[str, None]:
    """Crea una licitación de prueba. La limpia al final."""
    async with AsyncSessionLocal() as session:
        lic = Licitacion(
            codigo=_CODIGO_LIC,
            nombre="Licitación de prueba para checklist tests",
            estado=LicitacionEstado.publicada,
            moneda="CLP",
        )
        session.add(lic)
        await session.commit()

    yield _CODIGO_LIC

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Licitacion).where(Licitacion.codigo == _CODIGO_LIC)
        )
        lic_obj = result.scalar_one_or_none()
        if lic_obj is not None:
            await session.delete(lic_obj)
            await session.commit()


@pytest_asyncio.fixture
async def pipeline_item_de_usuario(
    db_session: AsyncSession,
    make_user: UserFactory,
    licitacion_prueba: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Crea usuario + empresa + pipeline_item para empresa A."""
    user = await make_user(
        email=f"empresa_a_{uuid.uuid4().hex[:6]}@test.cl",
        password="TestPass123!",
        razon_social="Empresa A SpA",
    )

    # Obtener empresa creada por make_user
    from app.models.empresa import Empresa
    emp_result = await db_session.execute(
        select(Empresa).where(Empresa.usuario_id == user.id)
    )
    empresa = emp_result.scalar_one()

    item = PipelineItem(
        empresa_id=empresa.id,
        licitacion_codigo=licitacion_prueba,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    yield {
        "user": user,
        "empresa": empresa,
        "pipeline_item": item,
        "email": user.email,
        "password": "TestPass123!",
    }

    # Cleanup
    async with AsyncSessionLocal() as cleanup_session:
        obj = await cleanup_session.get(PipelineItem, item.id)
        if obj is not None:
            await cleanup_session.delete(obj)
            await cleanup_session.commit()


@pytest.mark.asyncio
async def test_crud_checklist_completo(
    client: AsyncClient,
    pipeline_item_de_usuario: dict[str, Any],
) -> None:
    """Flujo completo: crear, listar, actualizar estado a completado, eliminar."""
    pip = pipeline_item_de_usuario
    headers = await _get_auth_header(client, pip["email"], pip["password"])
    pipeline_item_id = str(pip["pipeline_item"].id)

    # Feature flag activo solo para este test
    original = settings.feature_pipeline_checklist
    settings.feature_pipeline_checklist = True  # type: ignore[misc]

    try:
        # 1. Crear ítem
        resp = await client.post(
            f"/api/v1/pipeline/{pipeline_item_id}/checklist",
            json={"nombre": "Certificado ISO 9001", "obligatorio": True},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        item_data = resp.json()
        item_id = item_data["id"]
        assert item_data["nombre"] == "Certificado ISO 9001"
        assert item_data["origen"] == "manual"
        assert item_data["estado"] == "pendiente"
        assert item_data["completed_at"] is None

        # 2. Listar — debe aparecer el ítem creado
        resp = await client.get(
            f"/api/v1/pipeline/{pipeline_item_id}/checklist",
            headers=headers,
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1
        assert any(i["id"] == item_id for i in items)

        # 3. Actualizar estado a 'completado' — completed_at debe setearse
        resp = await client.patch(
            f"/api/v1/pipeline/{pipeline_item_id}/checklist/{item_id}",
            json={"estado": "completado"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        updated = resp.json()
        assert updated["estado"] == "completado"
        assert updated["completed_at"] is not None

        # 4. Eliminar ítem
        resp = await client.delete(
            f"/api/v1/pipeline/{pipeline_item_id}/checklist/{item_id}",
            headers=headers,
        )
        assert resp.status_code == 204

        # 5. Verificar que ya no existe
        resp = await client.get(
            f"/api/v1/pipeline/{pipeline_item_id}/checklist",
            headers=headers,
        )
        assert resp.status_code == 200
        items_after = resp.json()
        assert not any(i["id"] == item_id for i in items_after)

    finally:
        settings.feature_pipeline_checklist = original  # type: ignore[misc]


@pytest.mark.asyncio
async def test_acceso_no_autorizado_checklist(
    client: AsyncClient,
    make_user: UserFactory,
    pipeline_item_de_usuario: dict[str, Any],
    db_session: AsyncSession,
    licitacion_prueba: str,
) -> None:
    """Empresa B no puede leer ni modificar el checklist de empresa A."""
    pip_a = pipeline_item_de_usuario
    pipeline_item_id_a = str(pip_a["pipeline_item"].id)

    # Crear empresa B con su propio pipeline_item
    user_b = await make_user(
        email=f"empresa_b_{uuid.uuid4().hex[:6]}@test.cl",
        password="TestPass123!",
        razon_social="Empresa B SpA",
        rut=f"77.{uuid.uuid4().int % 999_999:06d}-K",
    )
    headers_b = await _get_auth_header(client, user_b.email, "TestPass123!")

    original = settings.feature_pipeline_checklist
    settings.feature_pipeline_checklist = True  # type: ignore[misc]

    try:
        # B intenta GET del checklist de A → 403 o 404
        resp = await client.get(
            f"/api/v1/pipeline/{pipeline_item_id_a}/checklist",
            headers=headers_b,
        )
        assert resp.status_code in (403, 404), (
            f"Esperado 403 o 404, obtenido {resp.status_code}: {resp.text}"
        )

        # B intenta POST en checklist de A → 403 o 404
        resp = await client.post(
            f"/api/v1/pipeline/{pipeline_item_id_a}/checklist",
            json={"nombre": "Doc intruso"},
            headers=headers_b,
        )
        assert resp.status_code in (403, 404)

    finally:
        settings.feature_pipeline_checklist = original  # type: ignore[misc]


@pytest.mark.asyncio
async def test_cascade_delete_pipeline_item(
    client: AsyncClient,
    db_session: AsyncSession,
    pipeline_item_de_usuario: dict[str, Any],
) -> None:
    """Eliminar pipeline_item borra sus checklist_items en cascada."""
    pip = pipeline_item_de_usuario
    pipeline_item_id = pip["pipeline_item"].id

    original = settings.feature_pipeline_checklist
    settings.feature_pipeline_checklist = True  # type: ignore[misc]

    try:
        headers = await _get_auth_header(client, pip["email"], pip["password"])

        # Crear un ítem en el checklist
        resp = await client.post(
            f"/api/v1/pipeline/{pipeline_item_id}/checklist",
            json={"nombre": "Ítem que debe eliminarse en cascada"},
            headers=headers,
        )
        assert resp.status_code == 201
        item_id = resp.json()["id"]

        # Verificar que el ítem existe en la BD
        async with AsyncSessionLocal() as session:
            checklist_result = await session.execute(
                select(PipelineChecklistItem).where(
                    PipelineChecklistItem.id == uuid.UUID(item_id)
                )
            )
            assert checklist_result.scalar_one_or_none() is not None

        # Eliminar el pipeline_item directamente en la BD (CASCADE test)
        async with AsyncSessionLocal() as session:
            pi = await session.get(PipelineItem, pipeline_item_id)
            if pi is not None:
                await session.delete(pi)
                await session.commit()

        # Verificar que el checklist_item ya no existe (CASCADE funcionó)
        async with AsyncSessionLocal() as session:
            checklist_result = await session.execute(
                select(PipelineChecklistItem).where(
                    PipelineChecklistItem.id == uuid.UUID(item_id)
                )
            )
            assert checklist_result.scalar_one_or_none() is None, (
                "El checklist_item debería haberse eliminado en cascada con el pipeline_item"
            )

        # Marcar el pipeline_item como ya limpiado para evitar doble-delete en teardown
        pip["pipeline_item"]._already_deleted = True  # type: ignore[attr-defined]

    finally:
        settings.feature_pipeline_checklist = original  # type: ignore[misc]
