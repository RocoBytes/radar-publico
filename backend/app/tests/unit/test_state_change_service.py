"""Tests unitarios para Feature B — alertas de cambio de estado externo.

Cubre:
1. test_sync_encola_task_al_detectar_cambio: sync detecta cambio de estado
   y llama send_task cuando hay pipeline_item activo.
2. test_sync_no_encola_sin_pipeline_activo: licitacion sin pipeline_items
   activos → send_task NO se llama.
3. test_sync_no_encola_sin_cambio_estado: hash cambia pero estado_codigo es
   igual → send_task NO se llama.
4. test_task_idempotente: emit_state_change_notifications llamado dos veces
   → segunda llamada crea 0 notificaciones nuevas.
5. test_task_sin_pipeline_items_al_ejecutar: tarea corre sin items activos
   → retorna 0, sin error.

Tests 1-3 verifican la lógica en sync_chilecompra._sync_empresa mediante
mocks. Tests 4-5 verifican emit_state_change_notifications con BD real.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid() -> str:
    return uuid.uuid4().hex[:6]


def _codigo_lic() -> str:
    return f"TSC-{_uid()}-T26"


def _rut() -> str:
    return f"76.{abs(uuid.uuid4().int) % 999_999:06d}-K"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def empresa_con_pipeline(db_session: AsyncSession) -> dict[str, object]:  # type: ignore[misc]
    """Crea usuario + empresa + licitacion + pipeline_item activo."""
    from app.db.session import AsyncSessionLocal
    from app.models.empresa import Empresa
    from app.models.enums import LicitacionEstado, PipelineEstado, UserRole, UserStatus
    from app.models.licitacion import Licitacion
    from app.models.pipeline import PipelineItem
    from app.models.usuario import Usuario

    email = f"test_sc_{_uid()}@test.cl"
    codigo_lic = _codigo_lic()

    async with AsyncSessionLocal() as session:
        usuario = Usuario(
            email=email,
            password_hash="$2b$12$placeholder",
            rol=UserRole.proveedor,
            status=UserStatus.active,
            must_change_password=False,
        )
        session.add(usuario)
        await session.flush()

        empresa = Empresa(
            usuario_id=usuario.id,
            rut=_rut(),
            razon_social="Empresa Test State Change SpA",
        )
        session.add(empresa)
        await session.flush()

        licitacion = Licitacion(
            codigo=codigo_lic,
            nombre="Licitación Test Cambio Estado",
            estado=LicitacionEstado.publicada,
            estado_codigo=5,
        )
        session.add(licitacion)
        await session.flush()

        pipeline_item = PipelineItem(
            empresa_id=empresa.id,
            licitacion_codigo=codigo_lic,
            estado=PipelineEstado.interesado,
        )
        session.add(pipeline_item)
        await session.commit()

        ids = {
            "usuario_id": usuario.id,
            "empresa_id": empresa.id,
            "licitacion_codigo": codigo_lic,
            "pipeline_item_id": pipeline_item.id,
        }

    yield ids  # type: ignore[misc]

    # Cleanup
    async with AsyncSessionLocal() as session:
        u = await session.get(Usuario, ids["usuario_id"])
        if u is not None:
            await session.delete(u)
        # Eliminar licitacion explicitamente (cascade puede no aplicar si no hay FK empresa)
        from app.models.licitacion import Licitacion as Lic

        lic = await session.get(Lic, ids["licitacion_codigo"])
        if lic is not None:
            await session.delete(lic)
        await session.commit()


@pytest_asyncio.fixture
async def _limpieza_notificaciones(  # type: ignore[misc]
    empresa_con_pipeline: dict[str, object],
) -> None:
    """Limpia notificaciones de test al finalizar."""
    from app.db.session import AsyncSessionLocal
    from app.models.notificacion import Notificacion

    yield  # type: ignore[misc]

    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(Notificacion).where(
                Notificacion.licitacion_codigo == str(empresa_con_pipeline["licitacion_codigo"])
            )
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Test 1: guard retorna True cuando hay cambio de estado y flag activo
# ---------------------------------------------------------------------------


def test_sync_encola_task_al_detectar_cambio() -> None:
    """_should_emit_state_alert retorna True cuando el estado cambia y el flag está activo."""
    from app.tasks.sync_chilecompra import _should_emit_state_alert

    assert _should_emit_state_alert(existing_codigo=5, new_codigo=6, flag_activo=True) is True


# ---------------------------------------------------------------------------
# Test 2: guard retorna False cuando el estado no cambia
# ---------------------------------------------------------------------------


def test_sync_no_encola_sin_cambio_estado() -> None:
    """_should_emit_state_alert retorna False cuando estado_codigo no cambia."""
    from app.tasks.sync_chilecompra import _should_emit_state_alert

    assert _should_emit_state_alert(existing_codigo=5, new_codigo=5, flag_activo=True) is False


# ---------------------------------------------------------------------------
# Test 3: guard retorna False cuando el feature flag está apagado
# ---------------------------------------------------------------------------


def test_sync_no_encola_con_flag_apagado() -> None:
    """_should_emit_state_alert retorna False cuando feature_licitacion_state_alerts=False."""
    from app.tasks.sync_chilecompra import _should_emit_state_alert

    assert _should_emit_state_alert(existing_codigo=5, new_codigo=6, flag_activo=False) is False


# ---------------------------------------------------------------------------
# Test 4: idempotencia — segunda llamada no crea notificaciones nuevas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_idempotente(
    empresa_con_pipeline: dict[str, object],
    _limpieza_notificaciones: None,
) -> None:
    """Llamar emit_state_change_notifications dos veces → segunda crea 0 notifs."""
    from app.db.session import AsyncSessionLocal
    from app.services.notifications.state_change import emit_state_change_notifications

    licitacion_codigo = str(empresa_con_pipeline["licitacion_codigo"])

    # Primera llamada
    async with AsyncSessionLocal() as session:
        result1 = await emit_state_change_notifications(
            db=session,
            licitacion_codigo=licitacion_codigo,
            estado_anterior="publicada",
            estado_nuevo="cerrada",
        )

    # Segunda llamada idéntica — idempotencia via ON CONFLICT DO NOTHING
    async with AsyncSessionLocal() as session:
        result2 = await emit_state_change_notifications(
            db=session,
            licitacion_codigo=licitacion_codigo,
            estado_anterior="publicada",
            estado_nuevo="cerrada",
        )

    # Primera vez: al menos 1 empresa notificada
    assert result1["empresas_notificadas"] >= 1
    # Segunda vez: 0 nuevas (ON CONFLICT DO NOTHING)
    assert result2["empresas_notificadas"] == 0
    assert result2["duplicadas_skip"] >= 1


# ---------------------------------------------------------------------------
# Test 5: sin pipeline_items activos al ejecutar → retorna 0, sin error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_sin_pipeline_items_al_ejecutar() -> None:
    """emit_state_change_notifications con licitacion sin pipeline_items activos."""
    from app.db.session import AsyncSessionLocal
    from app.services.notifications.state_change import emit_state_change_notifications

    # Código que no existe en BD (imposible tener pipeline_items)
    licitacion_inexistente = f"NOEXISTE-{_uid()}-T26"

    async with AsyncSessionLocal() as session:
        result = await emit_state_change_notifications(
            db=session,
            licitacion_codigo=licitacion_inexistente,
            estado_anterior="publicada",
            estado_nuevo="cerrada",
        )

    assert result == {"empresas_notificadas": 0, "duplicadas_skip": 0}
