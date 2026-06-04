"""Tarea Celery: detección de renovaciones próximas.

Para cada empresa activa, busca licitaciones adjudicadas renovables cuyo
contrato termine dentro del horizonte configurado y genera una notificación
in_app de tipo oportunidad_futura si no existe una reciente.

Reglas de oro:
  - #12: Sin PII en logs.
  - #29: Idempotente — no duplica si ya existe notif en los últimos 30 días.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import exists, select
import structlog

from app.celery_app import celery_app
from app.models.enums import (
    LicitacionEstado,
    NotifCanal,
    NotifStatus,
    NotifTipo,
    TicketStatus,
)

logger = structlog.get_logger()

_HORIZONTE_DIAS = 180  # 6 meses por defecto
_DEDUP_DIAS = 30  # no re-notificar si ya existe notif en los últimos 30 días


async def _run() -> dict[str, int]:
    from app.db.session import AsyncSessionLocal
    from app.models.empresa import Empresa
    from app.models.licitacion import Licitacion
    from app.models.notificacion import Notificacion
    from app.models.ticket import TicketApi

    stats: dict[str, int] = {"notificaciones_creadas": 0, "ya_notificadas": 0, "empresas": 0}

    ahora = datetime.now(UTC)
    horizonte = ahora + timedelta(days=_HORIZONTE_DIAS)
    ventana_dedup = ahora - timedelta(days=_DEDUP_DIAS)

    # Empresas con ticket activo
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TicketApi.empresa_id).where(TicketApi.status == TicketStatus.active)
        )
        empresa_ids = [row[0] for row in result.all()]

    stats["empresas"] = len(empresa_ids)

    for empresa_id in empresa_ids:
        async with AsyncSessionLocal() as session:
            empresa: Empresa | None = await session.get(Empresa, empresa_id)
            if empresa is None:
                continue

            # Licitaciones adjudicadas renovables dentro del horizonte
            stmt = (
                select(Licitacion)
                .where(
                    Licitacion.es_renovable.is_(True),
                    Licitacion.estado == LicitacionEstado.adjudicada,
                    Licitacion.fecha_estimada_termino_contrato.is_not(None),
                    Licitacion.fecha_estimada_termino_contrato <= horizonte,
                    # No crear notif si ya existe una reciente para esta empresa + licitacion
                    ~exists(
                        select(Notificacion.id).where(
                            Notificacion.empresa_id == empresa_id,
                            Notificacion.tipo == NotifTipo.oportunidad_futura,
                            Notificacion.licitacion_codigo == Licitacion.codigo,
                            Notificacion.created_at >= ventana_dedup,
                        )
                    ),
                )
                .order_by(Licitacion.fecha_estimada_termino_contrato.asc())
                .limit(50)  # cap por empresa por ejecución
            )

            lics = list((await session.execute(stmt)).scalars().all())

            for lic in lics:
                dias = (lic.fecha_estimada_termino_contrato - ahora).days  # type: ignore[operator]
                nombre_truncado = (lic.nombre or "")[:80]

                notif = Notificacion(
                    empresa_id=empresa_id,
                    tipo=NotifTipo.oportunidad_futura,
                    canal=NotifCanal.in_app,
                    status=NotifStatus.pendiente,
                    titulo=f"Renovación próxima: {nombre_truncado}",
                    cuerpo=(
                        f"El contrato de la licitación {lic.codigo} vence "
                        f"en {dias} días. Puede ser una oportunidad de renovación."
                    ),
                    licitacion_codigo=lic.codigo,
                    datos={"dias_para_termino": dias},
                    programada_para=ahora,
                )
                session.add(notif)
                stats["notificaciones_creadas"] += 1

            await session.commit()

    return stats


@celery_app.task(  # type: ignore
    name="tasks.detecta_renovaciones.detecta_renovaciones",
    acks_late=True,
)
def detecta_renovaciones() -> dict[str, Any]:
    """Detecta contratos próximos a vencer y genera notificaciones oportunidad_futura.

    Corre diariamente vía beat. Idempotente: no duplica si ya existe
    una notificación en los últimos 30 días para el mismo par (empresa, licitación).

    Returns:
        Dict con contadores: notificaciones_creadas, ya_notificadas, empresas.
    """
    logger.info("detecta_renovaciones_start")
    result = asyncio.run(_run())
    logger.info("detecta_renovaciones_ok", **result)
    return result
