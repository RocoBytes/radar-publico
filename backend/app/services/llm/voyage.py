"""Cliente async para embeddings con Voyage AI.

Toda llamada a la API de Voyage pasa por este módulo.
Nunca importar voyageai directamente desde servicios o tareas.
"""

import time
from typing import Literal

import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)
import voyageai

from app.config import settings
from app.services.llm.exceptions import EmbeddingError, EmbeddingRateLimitError

logger = structlog.get_logger(__name__)


def _es_rate_limit(exc: Exception) -> bool:
    """Detecta si una excepción de voyageai corresponde a rate limit."""
    # Intentar por tipo específico si el SDK lo expone
    tipo = type(exc).__name__.lower()
    if "ratelimit" in tipo or "rate_limit" in tipo:
        return True
    # Fallback por mensaje (voyageai puede no exponer clase pública)
    mensaje = str(exc).lower()
    return "rate limit" in mensaje or "ratelimit" in mensaje or "429" in mensaje


# Reintentar solo EmbeddingError que NO sea EmbeddingRateLimitError.
# EmbeddingRateLimitError hereda de EmbeddingError, por eso hay que excluirla
# explícitamente: retry_if_not_exception_type actúa como NOT sobre el predicado.
_RETRY_POLICY = retry_if_exception_type(EmbeddingError) & retry_if_not_exception_type(
    EmbeddingRateLimitError
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=_RETRY_POLICY,
    reraise=True,
)
async def embed_batch(
    textos: list[str],
    input_type: Literal["document", "query"] = "document",
) -> list[list[float]]:
    """Embebe una lista de textos con Voyage AI.

    Retorna lista de vectores de dimensión 1024.
    El batch se divide automáticamente si supera voyage_max_batch_size.

    Args:
        textos: Lista de textos a embedder.
        input_type: Tipo de input para Voyage AI. "document" para indexación,
            "query" para consultas de búsqueda.

    Returns:
        Lista de vectores float de dimensión 1024, uno por texto.

    Raises:
        EmbeddingRateLimitError: Si la API retorna rate limit (no se reintenta).
        EmbeddingError: Para cualquier otro error de la API
            (se reintenta hasta 3 veces).
    """
    if not textos:
        return []

    client = voyageai.AsyncClient(api_key=settings.voyage_api_key)  # type: ignore[attr-defined]
    max_batch = settings.voyage_max_batch_size
    modelo = settings.voyage_model

    # Dividir en sub-batches si supera el límite
    sub_batches = [textos[i : i + max_batch] for i in range(0, len(textos), max_batch)]

    log = logger.bind(
        num_textos=len(textos),
        num_batches=len(sub_batches),
        model=modelo,
        input_type=input_type,
    )

    embeddings_acumulados: list[list[float]] = []
    inicio = time.monotonic()

    try:
        for batch in sub_batches:
            resultado = await client.embed(
                texts=batch,
                model=modelo,
                input_type=input_type,
            )
            embeddings_acumulados.extend(resultado.embeddings)  # type: ignore[arg-type]
    except Exception as exc:
        if _es_rate_limit(exc):
            log.warning("voyage_rate_limit", error=str(exc))
            raise EmbeddingRateLimitError(str(exc)) from exc
        log.error("voyage_embed_error", error=str(exc))
        raise EmbeddingError(str(exc)) from exc

    duracion_ms = int((time.monotonic() - inicio) * 1000)
    log.info(
        "voyage_embed_ok",
        num_embeddings=len(embeddings_acumulados),
        duracion_ms=duracion_ms,
    )

    return embeddings_acumulados
