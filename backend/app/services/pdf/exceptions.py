"""Excepciones del módulo de procesamiento de PDFs."""


class PdfParseError(Exception):
    """Error genérico de parseo — apto para autoretry en Celery."""


class PdfCorruptoError(PdfParseError):
    """El PDF está dañado o truncado — no reintentable."""


class PdfEscaneadoError(PdfParseError):
    """El PDF no tiene texto extraíble (probable escaneo) — no reintentable."""


class ChunkingError(Exception):
    """Error al chunkear texto — apto para autoretry."""
