"""Tarea Celery: recálculo de scores de relevancia para pipeline items.

Calcula (o recalcula) el score de cada pipeline_item de una empresa usando
el servicio de scoring `services/scoring/relevance.py`.

Diseño:
  - Toma un empresa_id como argumento; si se omite, despacha una tarea
    por empresa activa (fan-out).
  - Carga empresa (con intereses) y pipeline_items (con licitacion → items +
    organismo) en dos queries con selectinload para evitar N+1.
  - El scoring es síncrono (puro cómputo) — solo la I/O a la BD es async.
  - Actualiza score y score_justificacion en bulk al finalizar.

Reglas de oro:
  - #12: Sin PII en logs.
  - #19: Sin N+1 — selectinload en todos los niveles necesarios.
  - #29: Idempotente — re-ejecutar recalcula correctamente.
"""

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()


async def _recalcula_empresa(empresa_id: UUID) -> dict[str, int]:
    from app.db.session import AsyncSessionLocal
    from app.models.empresa import Empresa
    from app.models.licitacion import Licitacion
    from app.models.pipeline import PipelineItem
    from app.services.scoring.relevance import calcular_score

    stats: dict[str, int] = {"actualizados": 0, "sin_cambio": 0, "errores": 0}

    async with AsyncSessionLocal() as session:
        # Cargar empresa con intereses
        empresa: Empresa | None = await session.get(
            Empresa,
            empresa_id,
            options=[selectinload(Empresa.intereses)],
        )
        if empresa is None:
            logger.warning(
                "recalcula_scores_empresa_no_encontrada",
                empresa_id=str(empresa_id),
            )
            return stats

        # Cargar pipeline_items con licitacion → items + organismo (2 queries, sin N+1)
        resultado = await session.execute(
            select(PipelineItem)
            .where(PipelineItem.empresa_id == empresa_id)
            .options(
                selectinload(PipelineItem.licitacion).options(
                    selectinload(Licitacion.items),
                    selectinload(Licitacion.organismo),
                )
            )
        )
        items = list(resultado.scalars().all())

    if not items:
        return stats

    regiones = list(empresa.regiones_operacion or [])
    intereses = list(empresa.intereses)

    async with AsyncSessionLocal() as session:
        for item in items:
            try:
                score, justificacion = calcular_score(item.licitacion, intereses, regiones)
                if item.score == score:
                    stats["sin_cambio"] += 1
                    continue
                # Re-attach para que la sesión pueda rastrear los cambios
                item_db = await session.get(type(item), item.id)
                if item_db is None:
                    continue
                item_db.score = score
                item_db.score_justificacion = justificacion
                stats["actualizados"] += 1
            except Exception as exc:
                logger.error(
                    "recalcula_scores_item_error",
                    pipeline_item_id=str(item.id),
                    error=str(exc),
                )
                stats["errores"] += 1

        await session.commit()

    return stats


async def _fan_out() -> dict[str, Any]:
    """Despacha una tarea por empresa que tenga pipeline_items activos."""
    from sqlalchemy import distinct

    from app.db.session import AsyncSessionLocal
    from app.models.pipeline import PipelineItem

    async with AsyncSessionLocal() as session:
        resultado = await session.execute(select(distinct(PipelineItem.empresa_id)))
        empresa_ids = [str(eid) for (eid,) in resultado.all()]

    for eid in empresa_ids:
        celery_app.send_task(
            "tasks.recalcula_scores.recalcula_scores_empresa",
            args=[eid],
        )

    return {"empresas_encoladas": len(empresa_ids)}


@celery_app.task(  # type: ignore[misc]
    name="tasks.recalcula_scores.recalcula_scores_empresa",
    bind=True,
    acks_late=True,
    max_retries=3,
    retry_backoff=True,
)
def recalcula_scores_empresa(self: Any, empresa_id: str) -> dict[str, int]:
    """Recalcula los scores de todos los pipeline_items de una empresa.

    Args:
        empresa_id: UUID de la empresa en formato string.

    Returns:
        Dict con contadores: actualizados, sin_cambio, errores.
    """
    log = logger.bind(empresa_id=empresa_id)
    log.info("recalcula_scores_start")
    result = asyncio.run(_recalcula_empresa(UUID(empresa_id)))
    log.info("recalcula_scores_ok", **result)
    return result


@celery_app.task(  # type: ignore[misc]
    name="tasks.recalcula_scores.recalcula_scores_todas",
    acks_late=True,
)
def recalcula_scores_todas() -> dict[str, Any]:
    """Fan-out: encola recalcula_scores_empresa para cada empresa con pipeline items."""
    logger.info("recalcula_scores_todas_start")
    result = asyncio.run(_fan_out())
    logger.info("recalcula_scores_todas_ok", **result)
    return result
