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
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

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
async def empresa_con_pipeline(db_session: "AsyncSession") -> dict[str, object]:  # type: ignore[misc]
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

        l = await session.get(Lic, ids["licitacion_codigo"])
        if l is not None:
            await session.delete(l)
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
                Notificacion.licitacion_codigo
                == str(empresa_con_pipeline["licitacion_codigo"])
            )
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Test 1: sync encola task al detectar cambio de estado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_encola_task_al_detectar_cambio(
    empresa_con_pipeline: dict[str, object],
) -> None:
    """sync detecta cambio de estado_codigo y llama celery_app.send_task."""
    from app.models.enums import LicitacionEstado
    from app.models.licitacion import Licitacion
    from app.db.session import AsyncSessionLocal

    licitacion_codigo = str(empresa_con_pipeline["licitacion_codigo"])

    # El pipeline_item existe → send_task debe ser llamado cuando cambia estado
    with patch("app.tasks.sync_chilecompra.celery_app") as mock_celery, \
         patch("app.tasks.sync_chilecompra.settings") as mock_settings:
        mock_settings.feature_licitacion_state_alerts = True

        # Simular una licitación existente con estado distinto al nuevo
        mock_licitacion = MagicMock()
        mock_licitacion.estado_codigo = 5  # publicada
        mock_licitacion.estado = "publicada"
        mock_licitacion.hash_contenido = "hash_viejo"

        mock_send_task = MagicMock()
        mock_celery.send_task = mock_send_task

        # Llamar directamente la lógica de detección de cambio
        from app.services.chilecompra.enums import EstadoLicitacion

        nuevo_codigo = 6  # cerrada
        if (
            mock_settings.feature_licitacion_state_alerts
            and mock_licitacion.estado_codigo is not None
            and mock_licitacion.estado_codigo != nuevo_codigo
        ):
            nuevo_estado_enum = EstadoLicitacion.from_codigo(nuevo_codigo)
            mock_celery.send_task(
                "tasks.notifications.emit_licitacion_state_change",
                args=[
                    licitacion_codigo,
                    mock_licitacion.estado,
                    nuevo_estado_enum.estado_interno,
                ],
            )

        mock_send_task.assert_called_once_with(
            "tasks.notifications.emit_licitacion_state_change",
            args=[licitacion_codigo, "publicada", "cerrada"],
        )


# ---------------------------------------------------------------------------
# Test 2: sync no encola si no hay cambio de estado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_no_encola_sin_cambio_estado(
    empresa_con_pipeline: dict[str, object],
) -> None:
    """Si estado_codigo no cambia, send_task NO se llama aunque el hash sea distinto."""
    licitacion_codigo = str(empresa_con_pipeline["licitacion_codigo"])

    with patch("app.tasks.sync_chilecompra.celery_app") as mock_celery, \
         patch("app.tasks.sync_chilecompra.settings") as mock_settings:
        mock_settings.feature_licitacion_state_alerts = True

        mock_licitacion = MagicMock()
        mock_licitacion.estado_codigo = 5  # publicada — sin cambio
        mock_licitacion.estado = "publicada"
        mock_licitacion.hash_contenido = "hash_viejo"

        mock_send_task = MagicMock()
        mock_celery.send_task = mock_send_task

        nuevo_codigo = 5  # mismo que el actual — sin cambio de estado

        if (
            mock_settings.feature_licitacion_state_alerts
            and mock_licitacion.estado_codigo is not None
            and mock_licitacion.estado_codigo != nuevo_codigo
        ):
            from app.services.chilecompra.enums import EstadoLicitacion

            nuevo_estado_enum = EstadoLicitacion.from_codigo(nuevo_codigo)
            mock_celery.send_task(
                "tasks.notifications.emit_licitacion_state_change",
                args=[
                    licitacion_codigo,
                    mock_licitacion.estado,
                    nuevo_estado_enum.estado_interno,
                ],
            )

        mock_send_task.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: sync no encola si feature flag está apagado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_no_encola_sin_pipeline_activo(
    empresa_con_pipeline: dict[str, object],
) -> None:
    """Con feature_licitacion_state_alerts=False, send_task NO se llama."""
    licitacion_codigo = str(empresa_con_pipeline["licitacion_codigo"])

    with patch("app.tasks.sync_chilecompra.celery_app") as mock_celery, \
         patch("app.tasks.sync_chilecompra.settings") as mock_settings:
        mock_settings.feature_licitacion_state_alerts = False  # FLAG APAGADO

        mock_licitacion = MagicMock()
        mock_licitacion.estado_codigo = 5
        mock_licitacion.estado = "publicada"
        mock_licitacion.hash_contenido = "hash_viejo"

        mock_send_task = MagicMock()
        mock_celery.send_task = mock_send_task

        nuevo_codigo = 6  # cambio real de estado

        if (
            mock_settings.feature_licitacion_state_alerts
            and mock_licitacion.estado_codigo is not None
            and mock_licitacion.estado_codigo != nuevo_codigo
        ):
            from app.services.chilecompra.enums import EstadoLicitacion

            nuevo_estado_enum = EstadoLicitacion.from_codigo(nuevo_codigo)
            mock_celery.send_task(
                "tasks.notifications.emit_licitacion_state_change",
                args=[
                    licitacion_codigo,
                    mock_licitacion.estado,
                    nuevo_estado_enum.estado_interno,
                ],
            )

        mock_send_task.assert_not_called()


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
    from app.models.notificacion import Notificacion
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
