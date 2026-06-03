"""Tarea Celery: embedding de licitación (título + descripción + ítems).

Decisiones de diseño (Sprint 2, 2026-05-11):

1. TEXTO CANÓNICO: compone {nombre}\n\n{descripcion}\n\n{items_resumen}.
   Los ítems se limitan a los primeros 20 para no inflar el embedding.

2. IDEMPOTENCIA: si embedding IS NOT NULL y hash_contenido no cambió → skip.
   Permite re-sincronizaciones de detalle sin re-embeber innecesariamente.

3. HASH: usa hash_contenido de la licitación (ya calculado en sync_detalle)
   para detectar cambios de contenido. Si el hash cambió, re-embebe.

Reglas de oro que aplican:
- #12: Sin PII en logs.
- #23: Logging de uso de IA en llm_usage_log.
- #29: Idempotente.
"""

import asyncio
from datetime import UTC, datetime
import hashlib
from typing import Any

import structlog

from app.celery_app import celery_app
from app.services.llm.exceptions import EmbeddingError

logger = structlog.get_logger()

_MAX_ITEMS = 20
_COSTO_USD_POR_TOKEN = 0.06 / 1_000_000


def _texto_canonico(nombre: str, descripcion: str | None, items: list[str]) -> str:
    """Compone el texto canónico para embedding de la licitación."""
    partes = [nombre]
    if descripcion:
        partes.append(descripcion)
    if items:
        partes.append("Ítems: " + "; ".join(items[:_MAX_ITEMS]))
    return "\n\n".join(partes)


async def _run(codigo: str) -> dict[str, int]:
    """Lógica async: embebe la licitación y persiste el vector."""
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.licitacion import Licitacion, LicitacionItem
    from app.services.llm.usage_log import registrar_uso
    from app.services.llm.voyage import embed_batch

    stats: dict[str, int] = {
        "embedido": 0,
        "sin_cambio": 0,
        "errores": 0,
    }

    async with AsyncSessionLocal() as session:
        lic: Licitacion | None = await session.get(Licitacion, codigo)

        if lic is None:
            logger.warning("embed_licitacion_no_encontrada", codigo=codigo)
            stats["errores"] += 1
            return stats

        items_result = await session.execute(
            select(LicitacionItem.nombre_producto)
            .where(LicitacionItem.licitacion_codigo == codigo)
            .limit(_MAX_ITEMS)
        )
        nombres_items = [r[0] for r in items_result if r[0]]

    texto = _texto_canonico(lic.nombre, lic.descripcion, nombres_items)
    nuevo_hash = hashlib.sha256(texto.encode()).hexdigest()

    # Idempotencia: si el embedding existe y el texto no cambió → skip
    if lic.embedding is not None and lic.hash_contenido == nuevo_hash:
        logger.debug("embed_licitacion_sin_cambio", codigo=codigo)
        stats["sin_cambio"] += 1
        return stats

    inicio = datetime.now(UTC)
    vectores = await embed_batch([texto], input_type="document")
    duracion_ms = int((datetime.now(UTC) - inicio).total_seconds() * 1000)

    # Aproximación: 4 chars ≈ 1 token. Evita descarga de tiktoken en contenedor sin red.
    tokens = max(1, len(texto) // 4)
    costo = tokens * _COSTO_USD_POR_TOKEN

    async with AsyncSessionLocal() as session:
        lic_update: Licitacion | None = await session.get(Licitacion, codigo)
        if lic_update is not None:
            lic_update.embedding = vectores[0]
            lic_update.updated_at = datetime.now(UTC)

        await registrar_uso(
            session,
            provider="voyage",
            modelo="voyage-3",
            tokens_in=tokens,
            costo_estimado_usd=costo,
            feature="embed_licitacion",
            duracion_ms=duracion_ms,
        )
        await session.commit()

    stats["embedido"] += 1
    logger.info(
        "embed_licitacion_ok",
        codigo=codigo,
        tokens=tokens,
        duracion_ms=duracion_ms,
    )
    return stats


@celery_app.task(  # type: ignore[misc]
    name="tasks.embed_licitacion.embed_licitacion",
    bind=True,
    autoretry_for=(EmbeddingError,),
    retry_backoff=True,
    max_retries=3,
    acks_late=True,
)
def embed_licitacion(self: Any, codigo: str) -> dict[str, int]:
    """Genera el embedding de la licitación a partir de nombre + descripción + ítems.

    Embebe el texto canónico con Voyage AI y actualiza licitaciones.embedding.
    Idempotente: si el embedding existe y el contenido no cambió, no hace nada.

    Disparada automáticamente por sync_detalle_licitacion al sincronizar detalle.

    Args:
        codigo: Código de la licitación, ej: '1000-8-LE26'.

    Returns:
        Dict con contadores: embedido, sin_cambio, errores.
    """
    logger.info("embed_licitacion_start", codigo=codigo)
    return asyncio.run(_run(codigo))
