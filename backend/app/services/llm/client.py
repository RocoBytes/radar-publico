"""Capa de abstracción LiteLLM para llamadas al LLM.

Toda llamada al LLM pasa por este módulo.
Nunca importar anthropic directamente desde endpoints o tareas.

Dos modos:
- chat_streaming(): para chat interactivo con SSE (respuesta incremental).
- completion(): para análisis estructurado (JSON) — no-streaming, retorna tokens usados.
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import litellm
import structlog

from app.config import settings
from app.services.llm.exceptions import LLMError, LLMRateLimitError

logger = structlog.get_logger(__name__)

_DEFAULT_MAX_TOKENS_STREAM: int = 1500
_DEFAULT_MAX_TOKENS_COMPLETION: int = 4096


@dataclass
class CompletionResult:
    """Resultado de una llamada completion no-streaming."""

    content: str
    tokens_in: int
    tokens_out: int
    modelo: str


async def chat_streaming(
    messages: list[dict[str, Any]],
    modelo: str | None = None,
    *,
    max_tokens: int = _DEFAULT_MAX_TOKENS_STREAM,
) -> AsyncGenerator[str, None]:
    """Genera respuesta en streaming usando LiteLLM + Anthropic.

    Args:
        messages: Lista de mensajes en formato OpenAI:
            [{"role": "...", "content": "..."}].
            Incluir el system prompt como primer mensaje con role="system".
        modelo: Override del modelo. Por defecto usa settings.llm_model_reasoning.
        max_tokens: Máximo de tokens en la respuesta. Default 1500 para chat.

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
        max_tokens=max_tokens,
        api_key=settings.anthropic_api_key,
    )

    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def completion(
    messages: list[dict[str, Any]],
    *,
    modelo: str | None = None,
    max_tokens: int = _DEFAULT_MAX_TOKENS_COMPLETION,
    temperature: float = 0.2,
) -> CompletionResult:
    """Genera respuesta no-streaming usando LiteLLM + Anthropic.

    Usar para análisis estructurado (JSON) — bases técnicas, borradores de propuesta.
    Para chat interactivo usar chat_streaming().

    Args:
        messages: Lista de mensajes en formato OpenAI.
        modelo: Override del modelo. Por defecto uses settings.llm_model_reasoning.
        max_tokens: Máximo de tokens. Default 4096, suficiente para JSON complejo.
        temperature: Default 0.2 para respuestas deterministas en análisis.

    Returns:
        CompletionResult con contenido, conteo de tokens y modelo usado.
        El caller es responsable de registrar el uso con usage_log.registrar_uso().

    Raises:
        LLMRateLimitError: Rate limit del proveedor.
        LLMError: Cualquier otro error de la API.
    """
    model_id = modelo or settings.llm_model_reasoning
    log = logger.bind(modelo=model_id, num_mensajes=len(messages))
    log.debug("completion_start")

    try:
        response = await litellm.acompletion(
            model=f"anthropic/{model_id}",
            messages=messages,
            stream=False,
            max_tokens=max_tokens,
            temperature=temperature,
            api_key=settings.anthropic_api_key,
        )
    except litellm.RateLimitError as exc:
        raise LLMRateLimitError(str(exc)) from exc
    except litellm.APIError as exc:
        raise LLMError(str(exc)) from exc

    content: str = response.choices[0].message.content or ""
    tokens_in: int = response.usage.prompt_tokens
    tokens_out: int = response.usage.completion_tokens

    log.debug("completion_ok", tokens_in=tokens_in, tokens_out=tokens_out)
    return CompletionResult(
        content=content,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        modelo=model_id,
    )
