"""Tarea Celery: embeddings de chunks de documento con Voyage AI.

Decisiones de diseño (Sprint 2, 2026-05-11):

1. IDEMPOTENCIA: selecciona solo chunks con embedding IS NULL para el documento.
   Re-encolar no re-embebe lo ya procesado.

2. BATCHING: embebe en sub-batches de voyage_max_batch_size (default 128).
   El bucle usa la misma función embed_batch que maneja la subdivisión.

3. COSTO: registra el uso en llm_usage_log (regla de oro #23).
   Estimación: voyage-3 cuesta ~$0.06/1M tokens.

4. CHAINING: al cerrar encola marcar_licitacion_procesada para la licitación.

Reglas de oro que aplican:
- #12: Sin PII en logs.
- #23: Logging de uso de IA en llm_usage_log.
- #29: Idempotente.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog

from app.celery_app import celery_app
from app.services.llm.exceptions import EmbeddingError

logger = structlog.get_logger()

# Costo aproximado por token de Voyage voyage-3 (dólares)
_COSTO_USD_POR_TOKEN = 0.06 / 1_000_000


async def _run(documento_id: str) -> dict[str, int]:
    """Lógica async: embebe los chunks pendientes de un documento."""
    import uuid

    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.documento_base import DocumentoBase, DocumentoChunk
    from app.services.llm.usage_log import registrar_uso
    from app.services.llm.voyage import embed_batch

    doc_uuid = uuid.UUID(documento_id)

    stats: dict[str, int] = {
        "embeddings_nuevos": 0,
        "sin_cambio": 0,
        "errores": 0,
    }

    # Cargar documento para obtener licitacion_codigo
    async with AsyncSessionLocal() as session:
        doc: DocumentoBase | None = await session.get(DocumentoBase, doc_uuid)

    if doc is None:
        logger.warning("embed_chunks_doc_no_encontrado", documento_id=documento_id)
        stats["errores"] += 1
        return stats

    licitacion_codigo = doc.licitacion_codigo

    # Obtener chunks sin embedding para este documento
    async with AsyncSessionLocal() as session:
        resultado = await session.execute(
            select(DocumentoChunk).where(
                DocumentoChunk.documento_id == doc_uuid,
                DocumentoChunk.embedding.is_(None),
            )
        )
        chunks_pendientes = list(resultado.scalars().all())

    if not chunks_pendientes:
        logger.debug("embed_chunks_sin_cambio", documento_id=documento_id)
        stats["sin_cambio"] += len(chunks_pendientes)
        return stats

    textos = [c.contenido for c in chunks_pendientes]
    inicio = datetime.now(UTC)

    vectores = await embed_batch(textos, input_type="document")

    duracion_ms = int((datetime.now(UTC) - inicio).total_seconds() * 1000)
    tokens_estimados = sum(c.tokens or 0 for c in chunks_pendientes)
    costo = tokens_estimados * _COSTO_USD_POR_TOKEN

    # Persistir embeddings en transacción
    async with AsyncSessionLocal() as session:
        for chunk, vector in zip(chunks_pendientes, vectores, strict=True):
            chunk_db: DocumentoChunk | None = await session.get(DocumentoChunk, chunk.id)
            if chunk_db is not None:
                chunk_db.embedding = vector

        await registrar_uso(
            session,
            provider="voyage",
            modelo="voyage-3",
            tokens_in=tokens_estimados,
            costo_estimado_usd=costo,
            feature="embed_chunks_documento",
            duracion_ms=duracion_ms,
        )
        await session.commit()

    stats["embeddings_nuevos"] = len(chunks_pendientes)
    logger.info(
        "embed_chunks_ok",
        documento_id=documento_id,
        embeddings_nuevos=len(chunks_pendientes),
        tokens_estimados=tokens_estimados,
        duracion_ms=duracion_ms,
    )

    # Encolar marcar_licitacion_procesada para verificar si la licitación completó
    celery_app.send_task(
        "tasks.marcar_procesada.marcar_licitacion_procesada",
        args=[licitacion_codigo],
    )

    return stats


@celery_app.task(  # type: ignore[untyped-decorator]
    name="tasks.embed_chunks.embed_chunks_documento",
    bind=True,
    autoretry_for=(EmbeddingError,),
    retry_backoff=True,
    max_retries=3,
    acks_late=True,
)
def embed_chunks_documento(self: Any, documento_id: str) -> dict[str, int]:
    """Genera embeddings para los chunks pendientes de un documento.

    Selecciona los DocumentoChunk con embedding=NULL para el documento dado,
    los embebe con Voyage AI en batches y actualiza la BD.

    Disparada automáticamente por procesar_pdf_documento al finalizar.

    Args:
        documento_id: UUID del DocumentoBase, en formato string.

    Returns:
        Dict con contadores: embeddings_nuevos, sin_cambio, errores.
    """
    logger.info("embed_chunks_start", documento_id=documento_id)
    return asyncio.run(_run(documento_id))
