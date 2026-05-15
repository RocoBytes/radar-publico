"""Capa de abstracción LiteLLM para chat con streaming.

Toda llamada al LLM de chat pasa por este módulo.
Nunca importar anthropic directamente desde endpoints o tareas.
"""

from collections.abc import AsyncGenerator
from typing import Any

import litellm
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

_CHAT_TEMPERATURE = 0.3
_MAX_TOKENS = 1500


async def chat_streaming(
    messages: list[dict[str, Any]],
    modelo: str | None = None,
) -> AsyncGenerator[str, None]:
    """Genera respuesta en streaming usando LiteLLM + Anthropic.

    Args:
        messages: Lista de mensajes en formato OpenAI:
            [{"role": "...", "content": "..."}].
            Incluir el system prompt como primer mensaje con role="system".
        modelo: Override del modelo. Por defecto usa settings.llm_model_reasoning.

    Yields:
        Fragmentos de texto (deltas) del stream.

    Raises:
        Exception: Cualquier error de la API. El caller debe capturar.
    """
    model_id = modelo or settings.llm_model_reasoning

    log = logger.bind(modelo=model_id, num_mensajes=len(messages))
    log.debug("chat_streaming_start")

    response = await litellm.acompletion(
        model=f"anthropic/{model_id}",
        messages=messages,
        stream=True,
        temperature=_CHAT_TEMPERATURE,
        max_tokens=_MAX_TOKENS,
        api_key=settings.anthropic_api_key,
    )

    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
