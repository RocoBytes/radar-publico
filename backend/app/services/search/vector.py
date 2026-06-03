"""Búsqueda vectorial sobre documento_chunks con pgvector."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.documento_base import DocumentoChunk
from app.services.llm.voyage import embed_batch

logger = structlog.get_logger(__name__)

_DEFAULT_TOP_K = 5


async def buscar_chunks_similares(
    db: AsyncSession,
    licitacion_codigo: str,
    query_text: str,
    top_k: int = _DEFAULT_TOP_K,
) -> list[DocumentoChunk]:
    """Busca los chunks más similares al query usando cosine distance (pgvector).

    1. Embebe el query con Voyage AI (input_type="query").
    2. Ordena los chunks por distancia coseno ascendente (operador <=> de pgvector).
    3. Retorna los top_k más similares.

    Args:
        db: Sesión async de SQLAlchemy.
        licitacion_codigo: Código de la licitación a consultar.
        query_text: Texto de búsqueda del usuario.
        top_k: Número máximo de chunks a retornar.

    Returns:
        Lista vacía si la licitación no tiene chunks embedidos.
    """
    vectores = await embed_batch([query_text], input_type="query")
    query_vec = vectores[0]

    result = await db.execute(
        select(DocumentoChunk)
        .where(
            DocumentoChunk.licitacion_codigo == licitacion_codigo,
            DocumentoChunk.embedding.isnot(None),
        )
        .order_by(DocumentoChunk.embedding.op("<=>")(query_vec))
        .limit(top_k)
    )
    chunks = list(result.scalars().all())

    logger.debug(
        "vector_search_ok",
        licitacion_codigo=licitacion_codigo,
        top_k=top_k,
        found=len(chunks),
    )
    return chunks
