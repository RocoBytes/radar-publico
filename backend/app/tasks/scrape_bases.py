"""Tarea Celery: scraping de documentos de bases desde el portal Mercado Público.

Decisiones de diseño (Sprint 2, 2026-05-11):

1. WORKER SEPARADO: la tarea usa la queue 'scraping' consumida por
   worker_scraper (imagen con browsers Playwright). Aísla el resource cost
   de Playwright y permite pausar el scraper sin afectar el sync de API.

2. IDEMPOTENCIA EN DOS NIVELES:
   - Nivel licitación: si bases_descargadas_at IS NOT NULL → sin_cambio.
   - Nivel documento: si ya existe row con mismo (licitacion_codigo, hash_contenido)
     → skip. Permite re-scrapes parciales cuando el portal agrega aclaraciones.

3. POLÍTICA DE ERRORES:
   - PortalPaginaNoEncontradaError → no reintento (404 semántico).
   - LicitacionSinBasesError       → no reintento; marcar bases_descargadas_at=now()
     con 0 docs (la licitación existe pero no publicó bases todavía).
   - PortalBloqueadoError          → no autoretry; alerta Sentry; requiere intervención.
   - ScrapingError / R2UploadError → autoretry con backoff exponencial (max 3).

4. CHAINING: disparada por sync_detalle_licitacion al completar el detalle.
   No importa la función de sync_detalle directamente para evitar ciclo de import.

Reglas de oro que aplican:
- #12: Sin PII en logs — solo loggear codigo y conteos.
- #29: Tarea idempotente — re-ejecutar no duplica filas ni archivos.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from app.celery_app import celery_app
from app.services.scraping.exceptions import (
    LicitacionSinBasesError,
    PortalBloqueadoError,
    PortalPaginaNoEncontradaError,
    ScrapingError,
)
from app.services.storage.exceptions import R2UploadError

logger = structlog.get_logger()


async def _run(codigo: str) -> dict[str, int]:
    """Lógica async del scraper.

    Descarga todos los PDFs adjuntos de la licitación, los sube a R2 y
    registra metadata en documentos_bases. Actualiza bases_descargadas_at.
    """

    from app.db.session import AsyncSessionLocal
    from app.models.licitacion import Licitacion
    from app.services.scraping.mercado_publico import extraer_adjuntos

    stats: dict[str, int] = {
        "descargados": 0,
        "sin_cambio": 0,
        "errores": 0,
        "sin_bases": 0,
        "no_encontrada": 0,
    }

    inicio = datetime.now(UTC)

    # Verificar idempotencia nivel licitación
    async with AsyncSessionLocal() as session:
        lic: Licitacion | None = await session.get(Licitacion, codigo)

    if lic is not None and lic.bases_descargadas_at is not None:
        logger.debug("scrape_bases_sin_cambio", codigo=codigo)
        stats["sin_cambio"] += 1
        return stats

    # Extraer lista de adjuntos del portal (Playwright)
    try:
        adjuntos = await extraer_adjuntos(codigo)
    except PortalPaginaNoEncontradaError:
        logger.warning("scrape_bases_pagina_no_encontrada", codigo=codigo)
        stats["no_encontrada"] += 1
        return stats
    except LicitacionSinBasesError:
        logger.info("scrape_bases_sin_bases", codigo=codigo)
        stats["sin_bases"] += 1
        # Marcar como procesado aunque no haya documentos — evita re-scrape
        async with AsyncSessionLocal() as session:
            lic = await session.get(Licitacion, codigo)
            if lic is not None:
                lic.bases_descargadas_at = datetime.now(UTC)
                lic.updated_at = datetime.now(UTC)
                await session.commit()
        return stats
    except PortalBloqueadoError as exc:
        logger.error(
            "scrape_bases_portal_bloqueado",
            codigo=codigo,
            error=str(exc),
        )
        stats["errores"] += 1
        raise  # No autoretry — re-elevar para que Celery lo deje en estado FAILURE

    # Descargar y subir cada adjunto
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as http:
        for adjunto in adjuntos:
            await _procesar_adjunto(
                http=http,
                codigo=codigo,
                adjunto=adjunto,
                stats=stats,
            )

    # Actualizar bases_descargadas_at en la licitación
    async with AsyncSessionLocal() as session:
        lic = await session.get(Licitacion, codigo)
        if lic is not None:
            lic.bases_descargadas_at = datetime.now(UTC)
            lic.updated_at = datetime.now(UTC)
            await session.commit()

    duracion_ms = int((datetime.now(UTC) - inicio).total_seconds() * 1000)
    logger.info(
        "scrape_bases_ok",
        codigo=codigo,
        descargados=stats["descargados"],
        sin_cambio=stats["sin_cambio"],
        errores=stats["errores"],
        duracion_ms=duracion_ms,
    )

    # Encolar procesar_pdf para cada doc recién descargado — evita import circular
    if stats["descargados"] > 0:
        from sqlalchemy import select

        from app.models.documento_base import DocumentoBase
        from app.models.enums import DocumentoStatus

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DocumentoBase.id).where(
                    DocumentoBase.licitacion_codigo == codigo,
                    DocumentoBase.status == DocumentoStatus.descargado,
                )
            )
            doc_ids = [str(row[0]) for row in result]

        for doc_id in doc_ids:
            celery_app.send_task(
                "tasks.procesar_pdf.procesar_pdf_documento",
                args=[doc_id],
                queue="scraping",
            )
            logger.debug("procesar_pdf_encolado", documento_id=doc_id)

    return stats


async def _procesar_adjunto(
    http: httpx.AsyncClient,
    codigo: str,
    adjunto: Any,
    stats: dict[str, int],
) -> None:
    """Descarga un adjunto, verifica idempotencia y sube a R2."""
    import hashlib

    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.documento_base import DocumentoBase
    from app.models.enums import DocumentoStatus
    from app.services.storage.r2 import subir_documento

    # Descargar el archivo
    try:
        response = await http.get(adjunto.url_origen)
        response.raise_for_status()
        contenido = response.content
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "scrape_bases_download_error",
            codigo=codigo,
            status=exc.response.status_code,
        )
        stats["errores"] += 1
        return
    except httpx.RequestError as exc:
        logger.warning(
            "scrape_bases_download_timeout",
            codigo=codigo,
            error=type(exc).__name__,
        )
        stats["errores"] += 1
        return

    if not contenido:
        stats["errores"] += 1
        return

    hash_contenido = hashlib.sha256(contenido).hexdigest()

    # Idempotencia nivel documento — mismo hash → ya procesado
    async with AsyncSessionLocal() as session:
        existing = (
            await session.execute(
                select(DocumentoBase).where(
                    DocumentoBase.licitacion_codigo == codigo,
                    DocumentoBase.hash_contenido == hash_contenido,
                )
            )
        ).scalar_one_or_none()

    if existing is not None:
        logger.debug(
            "scrape_bases_doc_sin_cambio",
            codigo=codigo,
            hash=hash_contenido[:8],
        )
        stats["sin_cambio"] += 1
        return

    # Validar tamaño
    from app.services.storage.r2 import MAX_TAMANO_BYTES

    if len(contenido) > MAX_TAMANO_BYTES:
        logger.warning(
            "scrape_bases_doc_demasiado_grande",
            codigo=codigo,
            tamano_bytes=len(contenido),
        )
        async with AsyncSessionLocal() as session:
            doc = DocumentoBase(
                licitacion_codigo=codigo,
                tipo=adjunto.tipo,
                nombre_original=adjunto.nombre[:500],
                url_origen=adjunto.url_origen,
                hash_contenido=hash_contenido,
                status=DocumentoStatus.error,
                error_mensaje=f"Archivo supera tamaño máximo ({len(contenido)} bytes)",
            )
            session.add(doc)
            await session.commit()
        stats["errores"] += 1
        return

    # Subir a R2
    try:
        result = await subir_documento(contenido, codigo)
    except R2UploadError:
        stats["errores"] += 1
        raise  # autoretry vía ScrapingError / R2UploadError en el decorador

    # Persistir metadata en documentos_bases
    async with AsyncSessionLocal() as session:
        doc = DocumentoBase(
            licitacion_codigo=codigo,
            tipo=adjunto.tipo,
            nombre_original=adjunto.nombre[:500],
            url_origen=adjunto.url_origen,
            storage_path=result.storage_path,
            storage_bucket=result.storage_bucket,
            mime_type=result.mime_type,
            tamano_bytes=result.tamano_bytes,
            hash_contenido=result.hash_sha256,
            status=DocumentoStatus.descargado,
            descargado_at=datetime.now(UTC),
        )
        session.add(doc)
        await session.commit()

    stats["descargados"] += 1


@celery_app.task(  # type: ignore
    name="tasks.scrape_bases.scrape_bases_licitacion",
    bind=True,
    autoretry_for=(ScrapingError, R2UploadError),
    retry_backoff=True,
    max_retries=3,
    acks_late=True,
    queue="scraping",
)
def scrape_bases_licitacion(self: Any, codigo: str) -> dict[str, int]:
    """Descarga los documentos de bases de una licitación desde el portal.

    Navega el portal Mercado Público con Playwright, descarga los PDFs
    adjuntos, los sube a R2 y registra metadata en documentos_bases.

    Disparada automáticamente por sync_detalle_licitacion al completar
    la sincronización del detalle.

    Args:
        codigo: Código de la licitación, ej: '1000-8-LE26'.

    Returns:
        Dict con contadores: descargados, sin_cambio, errores, sin_bases, no_encontrada.
    """
    logger.info("scrape_bases_start", codigo=codigo)
    return asyncio.run(_run(codigo))
