"""Tarea Celery: ejecución de radares activos.

Un radar es una búsqueda guardada con filtros JSONB. Esta tarea:
1. Aplica los filtros del radar sobre licitaciones en estado 'publicada'.
2. Para cada licitación que no esté ya en el pipeline de la empresa,
   crea un PipelineItem con estado 'nueva' y calcula su score.
3. Actualiza radar.ultima_ejecucion_at al finalizar.

Diseño:
  - ejecutar_radar(radar_id): procesa un radar específico.
  - ejecuta_radares_diarios(): fan-out — encola un ejecutar_radar por cada radar activo.
  - Sólo considera licitaciones publicadas DESPUÉS de ultima_ejecucion_at
    (o las últimas 24 h si el radar nunca se ejecutó).
  - Sin N+1: selectinload en empresa.intereses; EXISTS para verificar pipeline.

Reglas de oro:
  - #12: Sin PII en logs.
  - #19: Sin N+1.
  - #29: Idempotente — si ya existe pipeline_item, no lo duplica.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import selectinload
import structlog

from app.celery_app import celery_app
from app.models.enums import LicitacionEstado, NotifCanal, NotifStatus, NotifTipo

logger = structlog.get_logger()

_VENTANA_INICIAL_HORAS = 24


async def _ejecutar_radar(radar_id: UUID) -> dict[str, int]:
    from app.db.session import AsyncSessionLocal
    from app.models.empresa import Empresa
    from app.models.licitacion import Licitacion, LicitacionItem
    from app.models.notificacion import Notificacion
    from app.models.pipeline import PipelineItem
    from app.models.radar import Radar
    from app.services.scoring.relevance import calcular_score

    stats: dict[str, int] = {"nuevos": 0, "ya_existentes": 0, "errores": 0}

    async with AsyncSessionLocal() as session:
        radar: Radar | None = await session.get(Radar, radar_id)
        if radar is None or not radar.activo:
            return stats

        empresa: Empresa | None = await session.get(
            Empresa,
            radar.empresa_id,
            options=[selectinload(Empresa.intereses)],
        )
        if empresa is None:
            return stats

        # Fecha desde la cual buscar licitaciones nuevas
        desde = radar.ultima_ejecucion_at or (
            datetime.now(UTC) - timedelta(hours=_VENTANA_INICIAL_HORAS)
        )

        filtros: dict[str, Any] = radar.filtros or {}

        # Construir query base: publicadas después de `desde`
        stmt = (
            select(Licitacion)
            .where(
                Licitacion.estado == LicitacionEstado.publicada,
                Licitacion.fecha_publicacion >= desde,
                # Excluir licitaciones que ya tienen pipeline_item para esta empresa
                ~exists(
                    select(PipelineItem.id).where(
                        PipelineItem.empresa_id == empresa.id,
                        PipelineItem.licitacion_codigo == Licitacion.codigo,
                    )
                ),
            )
            .options(
                selectinload(Licitacion.items),
                selectinload(Licitacion.organismo),
            )
            .limit(500)  # cap por ejecución para evitar desborde
        )

        # Aplicar filtros del radar
        if filtros.get("q"):
            stmt = stmt.where(Licitacion.nombre.ilike(f"%{filtros['q']}%"))
        if filtros.get("estado"):
            # El radar puede filtrar por un estado específico (override de publicada)
            try:
                estado_filtro = LicitacionEstado(filtros["estado"])
                stmt = stmt.where(Licitacion.estado == estado_filtro)
            except ValueError:
                pass
        if filtros.get("tipo"):
            stmt = stmt.where(Licitacion.tipo == filtros["tipo"])
        if filtros.get("monto_min") is not None:
            stmt = stmt.where(Licitacion.monto_estimado >= filtros["monto_min"])
        if filtros.get("monto_max") is not None:
            stmt = stmt.where(Licitacion.monto_estimado <= filtros["monto_max"])
        if filtros.get("unspsc_codigo"):
            stmt = stmt.where(
                exists(
                    select(LicitacionItem.id).where(
                        LicitacionItem.licitacion_codigo == Licitacion.codigo,
                        LicitacionItem.unspsc_codigo.like(f"{filtros['unspsc_codigo']}%"),
                    )
                )
            )

        resultado = await session.execute(stmt)
        licitaciones = list(resultado.scalars().all())

    if not licitaciones:
        async with AsyncSessionLocal() as session:
            radar_db = await session.get(Radar, radar_id)
            if radar_db is not None:
                radar_db.ultima_ejecucion_at = datetime.now(UTC)
                await session.commit()
        return stats

    regiones = list(empresa.regiones_operacion or [])
    intereses = list(empresa.intereses)

    async with AsyncSessionLocal() as session:
        for licitacion in licitaciones:
            try:
                # Verificar de nuevo dentro de la sesión de escritura (race condition)
                existing = await session.execute(
                    select(PipelineItem.id).where(
                        PipelineItem.empresa_id == empresa.id,
                        PipelineItem.licitacion_codigo == licitacion.codigo,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    stats["ya_existentes"] += 1
                    continue

                score, justificacion = calcular_score(licitacion, intereses, regiones)

                item = PipelineItem(
                    empresa_id=empresa.id,
                    licitacion_codigo=licitacion.codigo,
                    detected_by_radar_id=radar_id,
                    score=score,
                    score_justificacion=justificacion,
                )
                session.add(item)

                # Notificación nueva_oportunidad si cumple umbral de score
                notif_score_min = radar.notif_score_minimo
                if notif_score_min is None or score is None or score >= notif_score_min:
                    organismo_nombre: str = (
                        licitacion.organismo.nombre
                        if licitacion.organismo is not None
                        else "organismo desconocido"
                    )
                    # Determinar canal: solo email e in_app soportados
                    canal_str = radar.notif_canal
                    if canal_str in ("email", "in_app"):
                        canal = NotifCanal[canal_str]
                    else:
                        canal = NotifCanal.in_app

                    nombre_truncado = (licitacion.nombre or "")[:80]
                    notif = Notificacion(
                        empresa_id=radar.empresa_id,
                        tipo=NotifTipo.nueva_oportunidad,
                        canal=canal,
                        status=NotifStatus.pendiente,
                        titulo=f"Nueva oportunidad: {nombre_truncado}",
                        cuerpo=(
                            f"El radar '{radar.nombre}' detectó una nueva licitación "
                            f"de {organismo_nombre}."
                        ),
                        licitacion_codigo=licitacion.codigo,
                        radar_id=radar_id,
                        programada_para=datetime.now(UTC),
                    )
                    session.add(notif)

                stats["nuevos"] += 1
            except Exception as exc:
                logger.error(
                    "ejecuta_radar_item_error",
                    licitacion_codigo=licitacion.codigo,
                    error=str(exc),
                )
                stats["errores"] += 1

        # Actualizar ultima_ejecucion_at
        radar_db = await session.get(Radar, radar_id)
        if radar_db is not None:
            radar_db.ultima_ejecucion_at = datetime.now(UTC)

        await session.commit()

    return stats


async def _fan_out() -> dict[str, Any]:
    """Despacha ejecutar_radar por cada radar activo."""
    from app.db.session import AsyncSessionLocal
    from app.models.radar import Radar

    async with AsyncSessionLocal() as session:
        resultado = await session.execute(select(Radar.id).where(Radar.activo.is_(True)))
        radar_ids = [str(rid) for (rid,) in resultado.all()]

    for rid in radar_ids:
        celery_app.send_task(
            "tasks.ejecuta_radares.ejecutar_radar",
            args=[rid],
        )

    return {"radares_encolados": len(radar_ids)}


@celery_app.task(  # type: ignore[misc]
    name="tasks.ejecuta_radares.ejecutar_radar",
    bind=True,
    acks_late=True,
    max_retries=2,
    retry_backoff=True,
)
def ejecutar_radar(self: Any, radar_id: str) -> dict[str, int]:
    """Ejecuta un radar: detecta licitaciones nuevas y crea pipeline items.

    Args:
        radar_id: UUID del radar en formato string.

    Returns:
        Dict con contadores: nuevos, ya_existentes, errores.
    """
    log = logger.bind(radar_id=radar_id)
    log.info("ejecutar_radar_start")
    result = asyncio.run(_ejecutar_radar(UUID(radar_id)))
    log.info("ejecutar_radar_ok", **result)
    return result


@celery_app.task(  # type: ignore[misc]
    name="tasks.ejecuta_radares.ejecuta_radares_diarios",
    acks_late=True,
)
def ejecuta_radares_diarios() -> dict[str, Any]:
    """Fan-out: encola ejecutar_radar para cada radar activo."""
    logger.info("ejecuta_radares_diarios_start")
    result = asyncio.run(_fan_out())
    logger.info("ejecuta_radares_diarios_ok", **result)
    return result
