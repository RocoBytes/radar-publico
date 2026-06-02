"""Servicio de fan-out para alertas de cambio de estado externo de licitaciones.

Emite notificaciones in-app a todas las empresas con pipeline_items activos
cuando una licitación en ChileCompra cambia de estado.

Reglas de oro que aplican:
- #14: Auditoría en eventos_auditoria.
- #19: Sin N+1 — bulk operations para multi-empresa.
- #29: Idempotencia via ON CONFLICT DO NOTHING (uq_notif_state_change_dedup).
"""

from datetime import UTC, datetime
import uuid

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    LicitacionEstado,
    NotifCanal,
    NotifStatus,
    NotifTipo,
    PipelineEstado,
)
from app.models.eventos_auditoria import AuditAction, EventoAuditoria
from app.models.notificacion import Notificacion
from app.models.pipeline import PipelineItem

logger = structlog.get_logger()

# Estados de pipeline que ya no requieren alertas externas.
# La licitación importa sólo mientras el proveedor está activamente participando.
_ESTADOS_TERMINALES: frozenset[PipelineEstado] = frozenset(
    {
        PipelineEstado.postulada,
        PipelineEstado.adjudicada,
        PipelineEstado.perdida,
        PipelineEstado.descartada,
    }
)


async def emit_state_change_notifications(
    db: AsyncSession,
    licitacion_codigo: str,
    estado_anterior: str,
    estado_nuevo: str,
) -> dict[str, int]:
    """Fan-out de notificaciones de cambio de estado externo.

    Crea una notificación in-app por cada empresa que tiene un pipeline_item
    activo para la licitación indicada. Es completamente idempotente: llamadas
    repetidas con los mismos argumentos no generan duplicados gracias al
    índice único uq_notif_state_change_dedup.

    Args:
        db: Sesión async de SQLAlchemy.
        licitacion_codigo: Código externo de la licitación en ChileCompra.
        estado_anterior: Valor string del enum LicitacionEstado antes del cambio.
        estado_nuevo: Valor string del enum LicitacionEstado después del cambio.

    Returns:
        Dict con "empresas_notificadas" (inserts nuevos) y "duplicadas_skip"
        (conflictos ignorados por idempotencia).
    """
    # 1. Buscar pipeline_items activos para esta licitación (sin N+1)
    resultado = await db.execute(
        select(PipelineItem.id, PipelineItem.empresa_id)
        .where(PipelineItem.licitacion_codigo == licitacion_codigo)
        .where(PipelineItem.estado.notin_(_ESTADOS_TERMINALES))
    )
    items = resultado.all()

    if not items:
        logger.info(
            "state_change_no_active_items",
            licitacion_codigo=licitacion_codigo,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
        )
        return {"empresas_notificadas": 0, "duplicadas_skip": 0}

    item_ids: list[uuid.UUID] = []
    empresa_ids: list[uuid.UUID] = []
    # Deduplicar empresas (una empresa puede tener un solo item por licitación
    # por el UNIQUE, pero el código es robusto ante cambios futuros)
    seen_empresas: set[uuid.UUID] = set()
    for item_id, empresa_id in items:
        item_ids.append(item_id)
        if empresa_id not in seen_empresas:
            seen_empresas.add(empresa_id)
            empresa_ids.append(empresa_id)

    datos_notif = {
        "estado_anterior": estado_anterior,
        "estado_nuevo": estado_nuevo,
    }
    titulo = f"Licitación {licitacion_codigo}: estado cambió a {estado_nuevo}"
    cuerpo = (
        f"La licitación {licitacion_codigo} pasó de "
        f"'{estado_anterior}' a '{estado_nuevo}' en ChileCompra."
    )
    now = datetime.now(UTC)

    # 2. Bulk INSERT con ON CONFLICT DO NOTHING — idempotencia garantizada por BD
    filas_nuevas: list[dict[str, object]] = [
        {
            "id": uuid.uuid4(),
            "empresa_id": eid,
            "tipo": NotifTipo.cambio_estado_externo.value,
            "canal": NotifCanal.in_app.value,
            "status": NotifStatus.pendiente.value,
            "titulo": titulo,
            "cuerpo": cuerpo,
            "datos": datos_notif,
            "licitacion_codigo": licitacion_codigo,
            "programada_para": now,
            "created_at": now,
        }
        for eid in empresa_ids
    ]

    stmt = pg_insert(Notificacion).values(filas_nuevas)
    # El índice uq_notif_state_change_dedup cubre
    # (empresa_id, licitacion_codigo, datos->>'estado_anterior', datos->>'estado_nuevo')
    # WHERE tipo = 'cambio_estado_externo'
    stmt = stmt.on_conflict_do_nothing()
    result_proxy = await db.execute(stmt)
    empresas_notificadas = result_proxy.rowcount if result_proxy.rowcount >= 0 else 0
    duplicadas_skip = len(empresa_ids) - empresas_notificadas

    # 3. Bulk UPDATE ultimo_estado_licitacion en los pipeline_items activos
    if item_ids:
        # Convertir string a LicitacionEstado con fallback a desconocido
        try:
            nuevo_estado_enum = LicitacionEstado(estado_nuevo)
        except ValueError:
            nuevo_estado_enum = LicitacionEstado.desconocido
        await db.execute(
            update(PipelineItem)
            .where(PipelineItem.id.in_(item_ids))
            .values(ultimo_estado_licitacion=nuevo_estado_enum)
        )

    # 4. Auditoría — una entrada por empresa notificada
    if empresas_notificadas > 0:
        audit_rows = [
            EventoAuditoria(
                empresa_id=eid,
                accion=AuditAction.NOTIFICACION_CAMBIO_ESTADO_EXTERNO,
                recurso_tipo="licitacion",
                recurso_id=licitacion_codigo,
                info={
                    "estado_anterior": estado_anterior,
                    "estado_nuevo": estado_nuevo,
                },
            )
            for eid in empresa_ids
        ]
        db.add_all(audit_rows)

    await db.commit()

    logger.info(
        "state_change_notifications_emitted",
        licitacion_codigo=licitacion_codigo,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        empresas_notificadas=empresas_notificadas,
        duplicadas_skip=duplicadas_skip,
    )

    return {
        "empresas_notificadas": empresas_notificadas,
        "duplicadas_skip": duplicadas_skip,
    }
