"""Excepciones del cliente de ChileCompra.

Todas derivan de MercadoPublicoError para facilitar catch genérico.
"""


class MercadoPublicoError(Exception):
    """Error base del cliente de la API de Mercado Público."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(MercadoPublicoError):
    """La API respondió 429 Too Many Requests."""

    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__(
            "Rate limit excedido en API ChileCompra"
            + (f" — reintentar en {retry_after}s" if retry_after else ""),
            status_code=429,
        )
        self.retry_after = retry_after


class TicketInvalidoError(MercadoPublicoError):
    """El ticket de ChileCompra es inválido o expiró (401/403)."""

    def __init__(self, ticket_ultimos_4: str = "????") -> None:
        # Sin PII — solo los últimos 4 chars del ticket
        super().__init__(
            f"Ticket inválido o expirado (***{ticket_ultimos_4})",
            status_code=401,
        )
        self.ticket_ultimos_4 = ticket_ultimos_4


class CuotaExcedidaError(MercadoPublicoError):
    """Se superaron los 10.000 requests/día del ticket."""

    def __init__(self) -> None:
        super().__init__(
            "Cuota diaria de requests agotada (10.000/día por ticket)",
            status_code=429,
        )


class LicitacionNoEncontradaError(MercadoPublicoError):
    """La licitación solicitada no existe en la API."""

    def __init__(self, codigo: str) -> None:
        super().__init__(f"Licitación no encontrada: {codigo!r}", status_code=404)
        self.codigo = codigo


class TimeoutError(MercadoPublicoError):
    """La request a la API superó el tiempo de espera."""

    def __init__(self, endpoint: str) -> None:
        super().__init__(f"Timeout en endpoint: {endpoint!r}")
        self.endpoint = endpoint
