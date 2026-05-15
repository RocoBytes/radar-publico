"""Tarea Celery: procesar notificaciones pendientes.

Procesa hasta 50 notificaciones con status='pendiente' cuya
programada_para <= now(), en orden FIFO.

Canales soportados:
  - in_app: se marca como enviada de inmediato (el frontend la lee por polling).
  - email: se envía con el email sender; fallo capturado individualmente.
  - whatsapp: marcada como fallida con mensaje explicativo hasta implementación.

Regla de oro #29: idempotente — el WHERE status='pendiente' garantiza que
un reintento no vuelve a procesar notificaciones ya enviadas.
"""

import asyncio
from datetime import UTC, datetime

import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()

_BATCH_SIZE = 50


async def _procesar_notificaciones() -> dict[str, int]:
    """Procesa hasta 50 notificaciones pendientes por corrida."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.db.session import AsyncSessionLocal
    from app.models.empresa import Empresa
    from app.models.enums import NotifCanal, NotifStatus
    from app.models.notificacion import Notificacion
    from app.services.email import sender as email_sender

    stats: dict[str, int] = {"enviadas": 0, "fallidas": 0, "total": 0}
    now = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        resultado = await session.execute(
            select(Notificacion)
            .where(
                Notificacion.status == NotifStatus.pendiente,
                Notificacion.programada_para <= now,
            )
            .order_by(Notificacion.programada_para.asc())
            .limit(_BATCH_SIZE)
            .options(
                selectinload(Notificacion.empresa).selectinload(Empresa.usuario),
            )
        )
        notificaciones = list(resultado.scalars().all())

    stats["total"] = len(notificaciones)

    for notif in notificaciones:
        async with AsyncSessionLocal() as session:
            # Re-fetch dentro de la sesión de escritura para evitar doble procesado
            notif_db = await session.get(
                Notificacion,
                notif.id,
                options=[
                    selectinload(Notificacion.empresa).selectinload(Empresa.usuario),
                ],
            )
            if notif_db is None or notif_db.status != NotifStatus.pendiente:
                continue

            if notif_db.canal == NotifCanal.in_app:
                notif_db.status = NotifStatus.enviada
                notif_db.enviada_at = datetime.now(UTC)
                logger.info(
                    "notificacion_enviada_in_app",
                    notif_id=str(notif_db.id),
                    tipo=notif_db.tipo,
                )
                stats["enviadas"] += 1

            elif notif_db.canal == NotifCanal.email:
                try:
                    destinatario: str = notif_db.empresa.usuario.email
                    await email_sender.send_email(
                        to=destinatario,
                        subject=notif_db.titulo,
                        html=f"<p>{notif_db.cuerpo}</p>",
                        text=notif_db.cuerpo,
                    )
                    notif_db.status = NotifStatus.enviada
                    notif_db.enviada_at = datetime.now(UTC)
                    logger.info(
                        "notificacion_enviada_email",
                        notif_id=str(notif_db.id),
                        tipo=notif_db.tipo,
                    )
                    stats["enviadas"] += 1
                except Exception as exc:
                    notif_db.status = NotifStatus.fallida
                    notif_db.error_mensaje = str(exc)[:500]
                    logger.warning(
                        "notificacion_email_fallida",
                        notif_id=str(notif_db.id),
                        error=str(exc)[:200],
                    )
                    stats["fallidas"] += 1

            else:
                # WhatsApp no implementado aún
                notif_db.status = NotifStatus.fallida
                notif_db.error_mensaje = "WhatsApp no implementado aún"
                logger.warning(
                    "notificacion_canal_no_soportado",
                    notif_id=str(notif_db.id),
                    canal=notif_db.canal,
                )
                stats["fallidas"] += 1

            await session.commit()

    return stats


@celery_app.task(  # type: ignore[misc]
    name="tasks.procesar_notificaciones.procesar_notificaciones",
    bind=True,
    acks_late=True,
    max_retries=3,
    retry_backoff=True,
)
def procesar_notificaciones(self: object) -> dict[str, int]:
    """Procesa notificaciones pendientes: email, in_app y whatsapp.

    Returns:
        Dict con contadores: enviadas, fallidas, total.
    """
    logger.info("procesar_notificaciones_start")
    result = asyncio.run(_procesar_notificaciones())
    logger.info("procesar_notificaciones_ok", **result)
    return result
