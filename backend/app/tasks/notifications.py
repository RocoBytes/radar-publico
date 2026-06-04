"""Tareas Celery para el envío y fan-out de notificaciones.

Contiene:
- emit_licitacion_state_change: alertas de cambio de estado externo (Feature B).

Reglas de oro que aplican:
- #29: Idempotencia — reintentar no duplica notificaciones (ON CONFLICT DO NOTHING).
"""

import asyncio
from typing import Any

import structlog

from app.celery_app import celery_app
from app.config import settings

logger = structlog.get_logger()


@celery_app.task(  # type: ignore
    name="tasks.notifications.emit_licitacion_state_change",
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 minuto entre reintentos
    acks_late=True,
)
def emit_licitacion_state_change(
    self: Any,  # Celery task instance — sin stubs tipados
    licitacion_codigo: str,
    estado_anterior: str,
    estado_nuevo: str,
) -> dict[str, int]:
    """Emite notificaciones in-app a empresas con pipeline activo para la licitación.

    Idempotente: reintentos no generan duplicados gracias al índice único
    uq_notif_state_change_dedup. Se omite sin error si el feature flag está apagado.

    Args:
        licitacion_codigo: Código externo de la licitación (ej: "1234-56-L118").
        estado_anterior: Valor string del enum LicitacionEstado antes del cambio.
        estado_nuevo: Valor string del enum LicitacionEstado después del cambio.

    Returns:
        Dict con "empresas_notificadas", "duplicadas_skip" o "skipped" si el flag
        está apagado.
    """
    if not settings.feature_licitacion_state_alerts:
        logger.debug(
            "state_alerts_disabled_skip",
            licitacion_codigo=licitacion_codigo,
        )
        return {"skipped": 1}

    async def _run() -> dict[str, int]:
        from app.db.session import AsyncSessionLocal
        from app.services.notifications.state_change import (
            emit_state_change_notifications,
        )

        async with AsyncSessionLocal() as session:
            return await emit_state_change_notifications(
                db=session,
                licitacion_codigo=licitacion_codigo,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_nuevo,
            )

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error(
            "emit_state_change_task_failed",
            licitacion_codigo=licitacion_codigo,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            error=str(exc),
            retries=self.request.retries,
        )
        raise self.retry(exc=exc) from exc
