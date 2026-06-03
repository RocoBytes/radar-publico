"""Tarea Celery: marcar bases_procesadas_at cuando todos los documentos terminaron.

Reglas de oro que aplican:
- #12: Sin PII en logs.
- #29: Idempotente — re-ejecutar no duplica efectos.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()


async def _run(codigo: str) -> dict[str, int]:
    """Marca bases_procesadas_at si todos los documentos están en estado final."""
    from sqlalchemy import func, select

    from app.db.session import AsyncSessionLocal
    from app.models.documento_base import DocumentoBase
    from app.models.enums import DocumentoStatus
    from app.models.licitacion import Licitacion

    stats: dict[str, int] = {"marcada": 0, "pendiente": 0, "sin_cambio": 0}

    async with AsyncSessionLocal() as session:
        lic: Licitacion | None = await session.get(Licitacion, codigo)

        if lic is None:
            return stats

        if lic.bases_procesadas_at is not None:
            stats["sin_cambio"] += 1
            return stats

        # Verificar que no haya documentos en estados no terminales
        result = await session.execute(
            select(func.count()).where(
                DocumentoBase.licitacion_codigo == codigo,
                DocumentoBase.status.in_([DocumentoStatus.pendiente, DocumentoStatus.descargado]),
            )
        )
        pendientes = result.scalar_one()

        if pendientes > 0:
            logger.debug(
                "marcar_procesada_pendiente",
                codigo=codigo,
                pendientes=pendientes,
            )
            stats["pendiente"] += 1
            return stats

        lic.bases_procesadas_at = datetime.now(UTC)
        lic.updated_at = datetime.now(UTC)
        await session.commit()

    stats["marcada"] += 1
    logger.info("marcar_procesada_ok", codigo=codigo)

    # Encolar análisis LLM de bases ahora que todos los chunks están disponibles
    celery_app.send_task(
        "tasks.analizar_bases.analizar_bases_licitacion",
        args=[codigo],
    )

    return stats


@celery_app.task(  # type: ignore[misc]
    name="tasks.marcar_procesada.marcar_licitacion_procesada",
    bind=True,
    max_retries=3,
    acks_late=True,
)
def marcar_licitacion_procesada(self: Any, codigo: str) -> dict[str, int]:
    """Marca bases_procesadas_at cuando todos los docs de la licitación terminaron.

    Verifica que no queden documentos en estado pendiente o descargado.
    Si todos están procesados o con error, sella bases_procesadas_at = now().

    Disparada automáticamente por embed_chunks_documento al cerrar.

    Args:
        codigo: Código de la licitación, ej: '1000-8-LE26'.

    Returns:
        Dict con contadores: marcada, pendiente, sin_cambio.
    """
    logger.info("marcar_procesada_start", codigo=codigo)
    return asyncio.run(_run(codigo))
