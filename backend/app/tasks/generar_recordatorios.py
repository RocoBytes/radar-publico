"""Tarea Celery: generar recordatorios de cierre de licitaciones.

Busca PipelineItems activos cuya licitación cierra en las próximas 24 horas
y crea notificaciones de tipo 'recordatorio_cierre' si aún no existen.

Ventanas implementadas en v1:
  - 24h: licitaciones que cierran entre now() y now() + 25h (ventana holgada).

Regla de oro #29: idempotente — verifica existencia antes de insertar.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()

_VENTANA_24H_MIN = 22  # horas mínimas para considerar ventana de 24h
_VENTANA_24H_MAX = 26  # horas máximas para considerar ventana de 24h
_DEDUP_HORAS = 20  # ventana de dedup: no crear si ya hay una en las últimas N horas


async def _generar_recordatorios() -> dict[str, int]:
    """Crea notificaciones de recordatorio para licitaciones que cierran en 24h."""
    from sqlalchemy import exists, select
    from sqlalchemy.orm import selectinload

    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifCanal, NotifStatus, NotifTipo, PipelineEstado
    from app.models.licitacion import Licitacion
    from app.models.notificacion import Notificacion
    from app.models.pipeline import PipelineItem

    stats: dict[str, int] = {"creadas": 0}
    now = datetime.now(UTC)
    ventana_inicio = now
    ventana_fin = now + timedelta(hours=_VENTANA_24H_MAX)
    dedup_desde = now - timedelta(hours=_DEDUP_HORAS)

    estados_excluidos = [
        PipelineEstado.descartada,
        PipelineEstado.perdida,
        PipelineEstado.adjudicada,
    ]

    async with AsyncSessionLocal() as session:
        resultado = await session.execute(
            select(PipelineItem)
            .join(Licitacion, PipelineItem.licitacion_codigo == Licitacion.codigo)
            .where(
                Licitacion.fecha_cierre >= ventana_inicio,
                Licitacion.fecha_cierre <= ventana_fin,
                PipelineItem.estado.not_in(estados_excluidos),
            )
            .options(
                selectinload(PipelineItem.licitacion),
            )
        )
        items = list(resultado.scalars().all())

    for item in items:
        licitacion = item.licitacion
        if licitacion.fecha_cierre is None:
            continue

        horas_restantes = (licitacion.fecha_cierre - now).total_seconds() / 3600

        # Solo ventana de 24h en v1
        if not (_VENTANA_24H_MIN <= horas_restantes <= _VENTANA_24H_MAX):
            continue

        async with AsyncSessionLocal() as session:
            # Deduplicar: no crear si ya existe una notificación reciente del mismo tipo
            ya_existe = await session.execute(
                select(
                    exists(Notificacion.id).where(
                        Notificacion.empresa_id == item.empresa_id,
                        Notificacion.licitacion_codigo == item.licitacion_codigo,
                        Notificacion.tipo == NotifTipo.recordatorio_cierre,
                        Notificacion.created_at >= dedup_desde,
                    )
                )
            )
            if ya_existe.scalar():
                continue

            nombre_truncado = licitacion.nombre[:80] if licitacion.nombre else ""
            fecha_str = licitacion.fecha_cierre.strftime("%d/%m/%Y %H:%M")

            # Siempre in_app; también crear notif email si corresponde (v1: solo in_app)
            notif = Notificacion(
                empresa_id=item.empresa_id,
                tipo=NotifTipo.recordatorio_cierre,
                canal=NotifCanal.in_app,
                status=NotifStatus.pendiente,
                titulo=f"Cierre en 24h: {nombre_truncado}",
                cuerpo=(
                    f"La licitación cierra el {fecha_str}. "
                    "Asegurate de completar tu postulación a tiempo."
                ),
                licitacion_codigo=item.licitacion_codigo,
                programada_para=now,
            )
            session.add(notif)

            try:
                await session.commit()
                stats["creadas"] += 1
                logger.info(
                    "recordatorio_cierre_creado",
                    licitacion_codigo=item.licitacion_codigo,
                    empresa_id=str(item.empresa_id),
                    horas_restantes=round(horas_restantes, 1),
                )
            except Exception as exc:
                await session.rollback()
                logger.warning(
                    "recordatorio_cierre_error",
                    licitacion_codigo=item.licitacion_codigo,
                    error=str(exc)[:200],
                )

    return stats


@celery_app.task(  # type: ignore
    name="tasks.generar_recordatorios.generar_recordatorios_cierre",
    bind=True,
    acks_late=True,
    max_retries=2,
    retry_backoff=True,
)
def generar_recordatorios_cierre(self: object) -> dict[str, int]:
    """Genera recordatorios de cierre para licitaciones que vencen en 24h.

    Returns:
        Dict con contador: creadas.
    """
    logger.info("generar_recordatorios_cierre_start")
    result = asyncio.run(_generar_recordatorios())
    logger.info("generar_recordatorios_cierre_ok", **result)
    return result
