"""Tarea Celery: procesar notificaciones pendientes.

Procesa hasta 50 notificaciones con status='pendiente' cuya
programada_para <= now(), en orden FIFO.

Canales soportados:
  - in_app: se marca como enviada de inmediato (el frontend la lee por polling).
  - email: se envía con el email sender; fallo capturado individualmente.
  - whatsapp: envía vía Twilio si WHATSAPP_ENABLED=true, respeta preferencias
    de la empresa (pausado_hasta, solo_criticas, score_minimo).

Regla de oro #29: idempotente — el WHERE status='pendiente' garantiza que
un reintento no vuelve a procesar notificaciones ya enviadas.
"""

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from app.celery_app import celery_app

if TYPE_CHECKING:
    from app.models.preferencias import PreferenciasNotificaciones

logger = structlog.get_logger()

_BATCH_SIZE = 50


# Tipos de notificación considerados "críticos" para whatsapp_solo_criticas.
_TIPOS_CRITICOS = frozenset(
    {
        "nueva_oportunidad",
        "adjudicacion_postulacion",
        "recordatorio_cierre",
        "oportunidad_futura",
    }
)


async def _procesar_notificaciones() -> dict[str, int]:
    """Procesa hasta 50 notificaciones pendientes por corrida."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.config import settings
    from app.db.session import AsyncSessionLocal
    from app.models.empresa import Empresa
    from app.models.enums import NotifCanal, NotifStatus
    from app.models.notificacion import Notificacion
    from app.services.email import sender as email_sender
    from app.services.whatsapp import sender as whatsapp_sender

    stats: dict[str, int] = {"enviadas": 0, "fallidas": 0, "canceladas": 0, "total": 0}
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
                selectinload(Notificacion.empresa).options(
                    selectinload(Empresa.usuario),
                    selectinload(Empresa.preferencias_notificaciones),
                ),
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
                    selectinload(Notificacion.empresa).options(
                        selectinload(Empresa.usuario),
                        selectinload(Empresa.preferencias_notificaciones),
                    ),
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

            elif notif_db.canal == NotifCanal.whatsapp:
                # 1. Feature flag — sin código activo hasta template Meta aprobado
                if not settings.whatsapp_enabled:
                    notif_db.status = NotifStatus.fallida
                    notif_db.error_mensaje = "whatsapp_deshabilitado"
                    stats["fallidas"] += 1
                    await session.commit()
                    continue

                prefs: PreferenciasNotificaciones | None = (
                    notif_db.empresa.preferencias_notificaciones
                )

                # 2. Canal WhatsApp inactivo en preferencias
                if prefs is not None and not prefs.whatsapp_activo:
                    notif_db.status = NotifStatus.cancelada
                    notif_db.error_mensaje = "whatsapp_inactivo_en_preferencias"
                    stats["canceladas"] += 1
                    await session.commit()
                    continue

                # 3. WhatsApp pausado temporalmente por la empresa
                if (
                    prefs is not None
                    and prefs.whatsapp_pausado_hasta is not None
                    and now < prefs.whatsapp_pausado_hasta
                ):
                    notif_db.status = NotifStatus.cancelada
                    notif_db.error_mensaje = (
                        f"whatsapp_pausado_hasta:{prefs.whatsapp_pausado_hasta.isoformat()}"
                    )
                    stats["canceladas"] += 1
                    await session.commit()
                    continue

                # 4. Filtro solo_criticas
                if (
                    prefs is not None
                    and prefs.whatsapp_solo_criticas
                    and notif_db.tipo.value not in _TIPOS_CRITICOS
                ):
                    notif_db.status = NotifStatus.cancelada
                    notif_db.error_mensaje = f"whatsapp_solo_criticas:tipo={notif_db.tipo.value}"
                    stats["canceladas"] += 1
                    await session.commit()
                    continue

                # 5. Verificar que la empresa tiene teléfono registrado
                telefono: str | None = notif_db.empresa.contacto_telefono
                if not telefono:
                    notif_db.status = NotifStatus.fallida
                    notif_db.error_mensaje = "whatsapp_sin_telefono"
                    stats["fallidas"] += 1
                    await session.commit()
                    continue

                # 6. Enviar
                try:
                    await whatsapp_sender.send_whatsapp(
                        to_number=telefono,
                        body=notif_db.cuerpo,
                    )
                    notif_db.status = NotifStatus.enviada
                    notif_db.enviada_at = datetime.now(UTC)
                    logger.info(
                        "notificacion_enviada_whatsapp",
                        notif_id=str(notif_db.id),
                        tipo=notif_db.tipo,
                    )
                    stats["enviadas"] += 1
                except Exception as exc:
                    notif_db.status = NotifStatus.fallida
                    notif_db.error_mensaje = str(exc)[:500]
                    logger.warning(
                        "notificacion_whatsapp_fallida",
                        notif_id=str(notif_db.id),
                        error=str(exc)[:200],
                    )
                    stats["fallidas"] += 1

            await session.commit()

    return stats


@celery_app.task(  # type: ignore
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
