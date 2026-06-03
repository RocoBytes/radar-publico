"""Excepciones del scraper de Mercado Público.

Jerarquía de errores:
- ScrapingError         → error transitorio, se auto-reintenta (timeout, 5xx)
- PortalBloqueadoError  → error permanente, requiere intervención humana
- LicitacionSinBasesError   → semántico: la licitación existe pero sin adjuntos
- PortalPaginaNoEncontradaError → semántico: página 404 en el portal
"""


class ScrapingError(Exception):
    """Error transitorio del scraper — apto para autoretry en Celery."""


class PortalBloqueadoError(Exception):
    """El portal bloqueó el acceso (captcha, 403, 429 persistente).

    No subclasifica ScrapingError para que NO sea auto-retentada.
    Requiere intervención manual (rotación de IP o contacto con Mercado Público).
    """


class LicitacionSinBasesError(Exception):
    """La licitación existe en el portal pero no tiene documentos adjuntos.

    Caso semántico esperado — no es un error y no se reintenta.
    """

    def __init__(self, codigo: str) -> None:
        super().__init__(f"Licitación {codigo!r} sin documentos adjuntos en el portal")
        self.codigo = codigo


class PortalPaginaNoEncontradaError(Exception):
    """La página de la licitación devolvió 404 en el portal.

    La licitación puede no existir en el portal aunque esté en la API.
    No se reintenta.
    """

    def __init__(self, codigo: str) -> None:
        super().__init__(f"Página de licitación no encontrada en portal: {codigo!r}")
        self.codigo = codigo
