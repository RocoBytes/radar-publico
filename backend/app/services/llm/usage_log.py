"""Registro de uso de modelos LLM en la base de datos.

Toda llamada a un proveedor de IA debe registrarse aquí para control de costos.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger(__name__)


async def registrar_uso(
    session: AsyncSession,
    *,
    provider: str,
    modelo: str,
    tokens_in: int,
    tokens_out: int = 0,
    costo_estimado_usd: float = 0.0,
    feature: str,
    empresa_id: uuid.UUID | None = None,
    duracion_ms: int | None = None,
    status: str = "ok",
    error_mensaje: str | None = None,
) -> None:
    """Registra una llamada a un LLM en llm_usage_log.

    Args:
        session: Sesión async de SQLAlchemy (no hace commit — la responsabilidad
            es del llamador o del contexto de transacción externo).
        provider: Nombre del proveedor (ej: "voyage", "anthropic").
        modelo: Identificador del modelo usado (ej: "voyage-3", "claude-opus-4-7").
        tokens_in: Tokens consumidos en la entrada / embedding.
        tokens_out: Tokens generados en la salida (0 para embeddings).
        costo_estimado_usd: Costo estimado en USD.
        feature: Nombre de la feature que originó la llamada (ej: "embed_licitacion").
        empresa_id: UUID de la empresa si la llamada es en contexto de un cliente.
        duracion_ms: Duración de la llamada en milisegundos.
        status: Estado de la llamada ("ok" o "error").
        error_mensaje: Mensaje de error si status="error".
    """
    await session.execute(
        text(
            """
            INSERT INTO llm_usage_log (
                empresa_id,
                feature,
                provider,
                modelo,
                tokens_input,
                tokens_output,
                costo_estimado,
                duracion_ms,
                status,
                error_mensaje
            ) VALUES (
                :empresa_id,
                :feature,
                :provider,
                :modelo,
                :tokens_input,
                :tokens_output,
                :costo_estimado,
                :duracion_ms,
                :status,
                :error_mensaje
            )
            """
        ),
        {
            "empresa_id": empresa_id,
            "feature": feature,
            "provider": provider,
            "modelo": modelo,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "costo_estimado": costo_estimado_usd if costo_estimado_usd else None,
            "duracion_ms": duracion_ms,
            "status": status,
            "error_mensaje": error_mensaje,
        },
    )

    logger.debug(
        "llm_uso_registrado",
        provider=provider,
        modelo=modelo,
        feature=feature,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        status=status,
    )
