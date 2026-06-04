"""Tarea Celery: parseo y chunking de documentos PDF descargados.

Decisiones de diseño (Sprint 2, 2026-05-11):

1. COLA DEFAULT: la tarea usa la queue default ('celery') consumida por los
   4 workers generales. pymupdf está en requirements-prod.txt, disponible para
   todos los workers. Esto libera los 2 workers del scraper (Playwright/Chromium)
   para que solo hagan scraping del portal.

2. IDEMPOTENCIA: si documentos_bases.status == 'procesado' → sin_cambio.
   Permite re-encolar sin duplicar chunks.

3. TEXTO_EXTRAIDO: solo se persisten los primeros 64 KB como preview para
   el panel admin. El texto completo vive distribuido en documento_chunks.

4. POLÍTICA DE ERRORES:
   - PdfEscaneadoError → status='error', no reintento.
   - PdfCorruptoError  → status='error', no reintento.
   - R2UploadError     → autoretry (fallo de descarga desde R2).
   - PdfParseError     → autoretry (error transitorio del parser).

5. CHAINING: al finalizar exitoso encola embed_chunks_documento (cola default).

Reglas de oro que aplican:
- #12: Sin PII en logs — solo doc_id y conteos.
- #29: Idempotente — re-ejecutar no duplica chunks.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog

from app.celery_app import celery_app
from app.services.pdf.exceptions import (
    PdfCorruptoError,
    PdfEscaneadoError,
    PdfParseError,
)
from app.services.storage.exceptions import R2UploadError

logger = structlog.get_logger()

_PREVIEW_BYTES = 64 * 1024  # 64 KB de texto como preview en documentos_bases


async def _run(documento_id: str) -> dict[str, int]:
    """Lógica async: descarga PDF de R2, parsea, chunkea y persiste chunks."""
    import uuid

    from sqlalchemy import delete

    from app.config import settings
    from app.db.session import AsyncSessionLocal
    from app.models.documento_base import DocumentoBase, DocumentoChunk
    from app.models.enums import DocumentoStatus
    from app.services.pdf.chunker import chunkear_documento
    from app.services.pdf.parser import parsear_pdf
    from app.services.storage.r2 import descargar_documento

    doc_uuid = uuid.UUID(documento_id)

    stats: dict[str, int] = {
        "procesado": 0,
        "sin_cambio": 0,
        "chunks_creados": 0,
        "errores": 0,
    }

    inicio = datetime.now(UTC)

    # Idempotencia: verificar estado actual
    async with AsyncSessionLocal() as session:
        doc: DocumentoBase | None = await session.get(DocumentoBase, doc_uuid)

    if doc is None:
        logger.warning("procesar_pdf_doc_no_encontrado", documento_id=documento_id)
        stats["errores"] += 1
        return stats

    if doc.status == DocumentoStatus.procesado:
        logger.debug("procesar_pdf_sin_cambio", documento_id=documento_id)
        stats["sin_cambio"] += 1
        return stats

    if doc.storage_path is None:
        logger.warning("procesar_pdf_sin_storage_path", documento_id=documento_id)
        stats["errores"] += 1
        return stats

    # Descargar bytes desde R2
    bucket = doc.storage_bucket or settings.r2_bucket
    contenido = await descargar_documento(doc.storage_path, bucket)

    # Parsear y chunkear
    try:
        parsed = await parsear_pdf(contenido)
    except (PdfEscaneadoError, PdfCorruptoError) as exc:
        # No reintentable — persistir error y salir
        async with AsyncSessionLocal() as session:
            doc_update: DocumentoBase | None = await session.get(DocumentoBase, doc_uuid)
            if doc_update is not None:
                doc_update.status = DocumentoStatus.error
                doc_update.error_mensaje = str(exc)
                doc_update.updated_at = datetime.now(UTC)  # type: ignore[attr-defined]
                await session.commit()
        logger.warning(
            "procesar_pdf_no_reintentable",
            documento_id=documento_id,
            tipo_error=type(exc).__name__,
        )
        stats["errores"] += 1
        return stats

    chunks = chunkear_documento(
        parsed.paginas,
        max_tokens=settings.pdf_chunk_tokens,
        overlap=settings.pdf_chunk_overlap,
    )

    # Texto preview (primeros 64 KB)
    texto_completo = "\n\n".join(parsed.paginas)
    texto_preview = texto_completo[:_PREVIEW_BYTES]

    # Persistir: borrar chunks anteriores (si re-procesamiento) + insertar nuevos
    async with AsyncSessionLocal() as session:
        await session.execute(delete(DocumentoChunk).where(DocumentoChunk.documento_id == doc_uuid))

        licitacion_codigo = doc.licitacion_codigo
        for chunk in chunks:
            session.add(
                DocumentoChunk(
                    documento_id=doc_uuid,
                    licitacion_codigo=licitacion_codigo,
                    chunk_orden=chunk.orden,
                    contenido=chunk.contenido,
                    pagina_inicio=chunk.pagina_inicio,
                    pagina_fin=chunk.pagina_fin,
                    tokens=chunk.tokens,
                    # embedding=NULL — se llena en embed_chunks_documento
                )
            )

        doc_update2: DocumentoBase | None = await session.get(DocumentoBase, doc_uuid)
        if doc_update2 is not None:
            doc_update2.status = DocumentoStatus.procesado
            doc_update2.procesado_at = datetime.now(UTC)
            doc_update2.num_paginas = parsed.num_paginas
            doc_update2.texto_extraido = texto_preview

        await session.commit()

    duracion_ms = int((datetime.now(UTC) - inicio).total_seconds() * 1000)
    stats["procesado"] += 1
    stats["chunks_creados"] = len(chunks)

    logger.info(
        "procesar_pdf_ok",
        documento_id=documento_id,
        num_paginas=parsed.num_paginas,
        chunks_creados=len(chunks),
        duracion_ms=duracion_ms,
    )

    # Encolar embed_chunks — evita import circular con send_task
    celery_app.send_task(
        "tasks.embed_chunks.embed_chunks_documento",
        args=[documento_id],
    )

    return stats


@celery_app.task(  # type: ignore
    name="tasks.procesar_pdf.procesar_pdf_documento",
    bind=True,
    autoretry_for=(R2UploadError, PdfParseError),
    retry_backoff=True,
    max_retries=3,
    acks_late=True,
    queue="celery",
)
def procesar_pdf_documento(self: Any, documento_id: str) -> dict[str, int]:
    """Parsea y chunkea un PDF descargado en R2.

    Descarga el PDF desde R2 usando el storage_path del documento, lo parsea
    con pymupdf, lo divide en chunks semánticos y persiste los chunks en
    documento_chunks (con embedding=NULL). Actualiza status a 'procesado'.

    Corre en la queue default ('celery'), consumida por los 4 workers generales.
    Disparada automáticamente por scrape_bases_licitacion para cada
    documento con status='descargado'.

    Args:
        documento_id: UUID del DocumentoBase, en formato string.

    Returns:
        Dict con contadores: procesado, sin_cambio, chunks_creados, errores.
    """
    logger.info("procesar_pdf_start", documento_id=documento_id)
    return asyncio.run(_run(documento_id))
