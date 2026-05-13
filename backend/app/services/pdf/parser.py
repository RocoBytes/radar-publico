"""Módulo de parseo de archivos PDF para Radar Público."""

import asyncio
from dataclasses import dataclass
import hashlib
import io

import fitz  # type: ignore[import-untyped]  # pymupdf
import magic
import structlog

from app.services.pdf.exceptions import PdfCorruptoError, PdfEscaneadoError

logger = structlog.get_logger(__name__)

_MIME_PDF = "application/pdf"
_UMBRAL_CHARS_POR_PAGINA = 50


@dataclass(frozen=True)
class ParsedPdf:
    """Resultado del parseo de un PDF."""

    paginas: list[str]
    num_paginas: int
    hash_contenido: str  # SHA-256 del contenido binario


def _extraer_con_pymupdf(contenido: bytes) -> list[str]:
    """Extrae texto página por página usando pymupdf.

    Raises:
        PdfCorruptoError: Si el PDF no puede abrirse o tiene 0 páginas.
    """
    try:
        doc = fitz.open(stream=contenido, filetype="pdf")
    except Exception as exc:
        raise PdfCorruptoError(f"pymupdf no pudo abrir el PDF: {exc}") from exc

    num_paginas = len(doc)
    if num_paginas == 0:
        raise PdfCorruptoError("El PDF no contiene páginas")

    return [doc[i].get_text("text") for i in range(num_paginas)]


def _promedio_chars(paginas: list[str]) -> float:
    """Calcula el promedio de caracteres por página."""
    if not paginas:
        return 0.0
    return sum(len(p) for p in paginas) / len(paginas)


def _extraer_con_unstructured(contenido: bytes) -> list[str]:
    """Intenta extraer texto usando unstructured como fallback para PDFs escaneados.

    Returns:
        Lista con un único elemento que contiene todo el texto concatenado,
        o lista vacía si no se extrajo nada.
    """
    from unstructured.partition.pdf import partition_pdf

    elementos = partition_pdf(file=io.BytesIO(contenido))
    texto = "\n\n".join(e.text for e in elementos if e.text and e.text.strip())
    return [texto] if texto.strip() else []


def _parsear_sincrono(contenido: bytes) -> ParsedPdf:
    """Parsea el PDF de forma síncrona (se invoca desde asyncio.to_thread).

    Raises:
        PdfCorruptoError: MIME incorrecto, PDF dañado o sin páginas.
        PdfEscaneadoError: PDF sin texto extraíble (probable escaneo).
    """
    # 1. Verificar MIME
    mime = magic.from_buffer(contenido, mime=True)
    if mime != _MIME_PDF:
        raise PdfCorruptoError(
            f"MIME incorrecto: esperado application/pdf, recibido {mime!r}"
        )

    # 2. Extraer con pymupdf
    paginas = _extraer_con_pymupdf(contenido)
    num_paginas = len(paginas)

    # 3. Heurística de escaneado
    if _promedio_chars(paginas) < _UMBRAL_CHARS_POR_PAGINA:
        logger.debug(
            "pdf.escaneado_sospechoso",
            num_paginas=num_paginas,
            promedio_chars=round(_promedio_chars(paginas), 1),
        )
        fallback = _extraer_con_unstructured(contenido)
        if not fallback:
            raise PdfEscaneadoError("PDF escaneado - OCR pendiente")
        paginas = fallback

    # 4. SHA-256 del contenido binario
    hash_contenido = hashlib.sha256(contenido).hexdigest()

    logger.info(
        "pdf.parseado",
        num_paginas=num_paginas,
        tamano_bytes=len(contenido),
    )

    return ParsedPdf(
        paginas=paginas,
        num_paginas=num_paginas,
        hash_contenido=hash_contenido,
    )


async def parsear_pdf(contenido: bytes) -> ParsedPdf:
    """Parsea un PDF y devuelve su contenido estructurado.

    El parseo es CPU-bound y se ejecuta en un thread separado para no
    bloquear el event loop de asyncio.

    Args:
        contenido: Bytes crudos del archivo PDF.

    Returns:
        ParsedPdf con el texto por página, cantidad de páginas y hash SHA-256.

    Raises:
        PdfCorruptoError: Si el archivo no es un PDF válido o está dañado.
        PdfEscaneadoError: Si el PDF no contiene texto extraíble (escaneo sin OCR).
    """
    return await asyncio.to_thread(_parsear_sincrono, contenido)
