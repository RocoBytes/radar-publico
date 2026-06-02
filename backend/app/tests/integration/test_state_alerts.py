"""Tests de integración para Feature B — alertas de cambio de estado externo.

Requiere:
- Postgres corriendo con schema cargado (incluyendo migración 20260603_1030).
- Variables de entorno de BD configuradas.

Cubre:
1. test_notificacion_emitida_por_empresa: N empresas con pipeline_items activos
   para la misma licitación → emit_state_change_notifications crea N notifs en BD.
2. test_campo_ultimo_estado_actualizado: después de emit_state_change_notifications,
   pipeline_items.ultimo_estado_licitacion = estado_nuevo.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.empresa import Empresa
from app.models.enums import (
    LicitacionEstado,
    NotifTipo,
    PipelineEstado,
    UserRole,
    UserStatus,
)
from app.models.licitacion import Licitacion
from app.models.notificacion import Notificacion
from app.models.pipeline import PipelineItem
from app.models.usuario import Usuario

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid() -> str:
    return uuid.uuid4().hex[:6]


def _rut() -> str:
    return f"76.{abs(uuid.uuid4().int) % 999_999:06d}-K"


def _email() -> str:
    return f"test_sa_{_uid()}@test.cl"


def _codigo_lic() -> str:
    return f"INTSA-{_uid()}-T26"


# ---------------------------------------------------------------------------
# Fixture: N empresas con pipeline activo para la misma licitación
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def setup_multi_empresa(  # type: ignore[misc]
    n: int = 3,
) -> AsyncGenerator[dict[str, object], None]:
    """Crea N usuarios + empresas + licitacion compartida + pipeline_items activos.

    Yield: dict con 'licitacion_codigo', 'empresa_ids', 'usuario_ids'.
    Limpia todo al finalizar.
    """
    codigo_lic = _codigo_lic()
    usuario_ids: list[uuid.UUID] = []
    empresa_ids: list[uuid.UUID] = []

    async with AsyncSessionLocal() as session:
        # Licitación compartida para las N empresas
        licitacion = Licitacion(
            codigo=codigo_lic,
            nombre="Licitación Integración Alertas",
            estado=LicitacionEstado.publicada,
            estado_codigo=5,
        )
        session.add(licitacion)
        await session.flush()

        for i in range(n):
            usuario = Usuario(
                email=_email(),
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
                razon_social=f"Empresa Alerta Test {i} SpA",
            )
            session.add(empresa)
            await session.flush()

            pipeline_item = PipelineItem(
                empresa_id=empresa.id,
                licitacion_codigo=codigo_lic,
                estado=PipelineEstado.postulando,  # activo — no es terminal
            )
            session.add(pipeline_item)

            usuario_ids.append(usuario.id)
            empresa_ids.append(empresa.id)

        await session.commit()

    yield {  # type: ignore[misc]
        "licitacion_codigo": codigo_lic,
        "empresa_ids": empresa_ids,
        "usuario_ids": usuario_ids,
        "n": n,
    }

    # Cleanup
    async with AsyncSessionLocal() as session:
        for uid in usuario_ids:
            u = await session.get(Usuario, uid)
            if u is not None:
                await session.delete(u)
        l = await session.get(Licitacion, codigo_lic)
        if l is not None:
            await session.delete(l)
        await session.commit()


# ---------------------------------------------------------------------------
# Test 1: notificacion emitida por empresa
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notificacion_emitida_por_empresa(
    setup_multi_empresa: dict[str, object],
) -> None:
    """emit_state_change_notifications crea 1 notif in_app por empresa activa."""
    from app.services.notifications.state_change import emit_state_change_notifications

    codigo_lic = str(setup_multi_empresa["licitacion_codigo"])
    empresa_ids: list[uuid.UUID] = list(setup_multi_empresa["empresa_ids"])  # type: ignore[arg-type]
    n = int(setup_multi_empresa["n"])  # type: ignore[arg-type]

    async with AsyncSessionLocal() as session:
        result = await emit_state_change_notifications(
            db=session,
            licitacion_codigo=codigo_lic,
            estado_anterior="publicada",
            estado_nuevo="cerrada",
        )

    # Debe haber notificado exactamente N empresas
    assert result["empresas_notificadas"] == n
    assert result["duplicadas_skip"] == 0

    # Verificar que las notificaciones existen en BD con el tipo correcto
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Notificacion)
                .where(Notificacion.licitacion_codigo == codigo_lic)
                .where(Notificacion.tipo == NotifTipo.cambio_estado_externo)
            )
        ).scalars().all()

    assert len(rows) == n
    # Verificar que las empresas notificadas son exactamente las del fixture
    notified_empresa_ids = {row.empresa_id for row in rows}
    assert notified_empresa_ids == set(empresa_ids)

    # Verificar payload de datos
    for row in rows:
        assert row.datos["estado_anterior"] == "publicada"
        assert row.datos["estado_nuevo"] == "cerrada"

    # Cleanup notificaciones
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete

        await session.execute(
            delete(Notificacion).where(Notificacion.licitacion_codigo == codigo_lic)
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Test 2: campo ultimo_estado_licitacion actualizado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_campo_ultimo_estado_actualizado(
    setup_multi_empresa: dict[str, object],
) -> None:
    """Después de emit_state_change_notifications, pipeline_items.ultimo_estado_licitacion
    refleja el estado nuevo."""
    from app.services.notifications.state_change import emit_state_change_notifications

    codigo_lic = str(setup_multi_empresa["licitacion_codigo"])
    empresa_ids: list[uuid.UUID] = list(setup_multi_empresa["empresa_ids"])  # type: ignore[arg-type]

    async with AsyncSessionLocal() as session:
        await emit_state_change_notifications(
            db=session,
            licitacion_codigo=codigo_lic,
            estado_anterior="publicada",
            estado_nuevo="cerrada",
        )

    # Verificar que todos los pipeline_items tienen ultimo_estado_licitacion = cerrada
    async with AsyncSessionLocal() as session:
        items = (
            await session.execute(
                select(PipelineItem).where(
                    PipelineItem.licitacion_codigo == codigo_lic
                )
            )
        ).scalars().all()

    assert len(items) == len(empresa_ids)
    for item in items:
        assert item.ultimo_estado_licitacion is not None
        assert str(item.ultimo_estado_licitacion) == "cerrada" or (
            hasattr(item.ultimo_estado_licitacion, "value")
            and item.ultimo_estado_licitacion.value == "cerrada"
        )

    # Cleanup notificaciones
    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete

        await session.execute(
            delete(Notificacion).where(Notificacion.licitacion_codigo == codigo_lic)
        )
        await session.commit()
