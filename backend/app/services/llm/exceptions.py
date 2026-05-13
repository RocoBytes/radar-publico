"""Excepciones del módulo LLM."""


class EmbeddingError(Exception):
    """Error genérico de embedding — apto para autoretry."""


class EmbeddingRateLimitError(EmbeddingError):
    """Rate limit de Voyage AI — apto para retry con backoff largo.

    No se reintenta automáticamente: debe subir para alerta en Sentry.
    """
