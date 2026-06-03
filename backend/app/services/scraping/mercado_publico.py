"""Scraper del portal Mercado Público para extraer adjuntos de licitaciones.

AVISO: Los selectores CSS/XPath del portal son frágiles y deben validarse
contra el DOM real antes del primer deploy. Inspeccionar con DevTools sobre:
  https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion={codigo}

El portal usa WebForms ASP.NET con tabs dinámicos. La sección de documentos
puede requerir un click en el tab antes de que los links sean visibles.
"""

import asyncio
from dataclasses import dataclass
import re

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
import structlog

from app.config import settings
from app.models.enums import DocumentoTipo
from app.services.scraping.exceptions import (
    LicitacionSinBasesError,
    PortalBloqueadoError,
    PortalPaginaNoEncontradaError,
    ScrapingError,
)
from app.services.scraping.playwright_client import playwright_page

logger = structlog.get_logger()

_PORTAL_BASE = "https://www.mercadopublico.cl"
_PORTAL_URL = (
    f"{_PORTAL_BASE}/Procurement/Modules/RFB/" "DetailsAcquisition.aspx?idlicitacion={codigo}"
)

# Indicadores de página de bloqueo/captcha
_INDICADORES_BLOQUEO = frozenset(
    ["captcha", "robot", "acceso denegado", "access denied", "forbidden"]
)

# Tamaño máximo de PDF permitido: 50 MB
MAX_TAMANO_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class AdjuntoLicitacion:
    """Metadatos de un documento adjunto extraído del portal."""

    nombre: str
    url_origen: str
    tipo: DocumentoTipo


async def extraer_adjuntos(codigo: str) -> list[AdjuntoLicitacion]:
    """Navega el portal y retorna la lista de adjuntos de una licitación.

    Args:
        codigo: Código de la licitación, ej: '1234-56-LR26'.

    Returns:
        Lista de AdjuntoLicitacion con nombre, URL y tipo inferido.

    Raises:
        PortalPaginaNoEncontradaError: El portal devolvió 404.
        PortalBloqueadoError: El portal detectó el scraper (403/429/captcha).
        LicitacionSinBasesError: La página existe pero no tiene adjuntos.
        ScrapingError: Error transitorio (timeout, 5xx) — apto para retry.
    """
    url = _PORTAL_URL.format(codigo=codigo)

    # Delay anti-bot — configurado en settings.scraping_delay_ms
    await asyncio.sleep(settings.scraping_delay_ms / 1000)

    async with playwright_page() as page:
        try:
            response = await page.goto(url, wait_until="domcontentloaded")
        except PlaywrightTimeoutError as e:
            raise ScrapingError(f"Timeout navegando portal para {codigo!r}") from e

        if response is None or response.status == 404:
            raise PortalPaginaNoEncontradaError(codigo)

        if response.status in (403, 429):
            raise PortalBloqueadoError(
                f"Portal bloqueó acceso (HTTP {response.status}) para {codigo!r}"
            )

        if response.status >= 500:
            raise ScrapingError(
                f"Error del servidor del portal " f"(HTTP {response.status}) para {codigo!r}"
            )

        # Detectar captcha / bloqueo en el contenido de la página
        try:
            body_text = await page.inner_text("body")
        except Exception:
            body_text = ""

        if any(ind in body_text.lower() for ind in _INDICADORES_BLOQUEO):
            raise PortalBloqueadoError(f"Portal requiere verificación humana para {codigo!r}")

        adjuntos = await _extraer_links_documentos(page, codigo)

        if not adjuntos:
            raise LicitacionSinBasesError(codigo)

        logger.debug(
            "scraper_adjuntos_encontrados",
            codigo=codigo,
            cantidad=len(adjuntos),
        )
        return adjuntos


async def _extraer_links_documentos(page: Page, codigo: str) -> list[AdjuntoLicitacion]:
    """Extrae los links de descarga de documentos de la página.

    Estrategia en capas:
    1. Intentar activar el tab de documentos (si el portal usa tabs)
    2. Buscar links con selectores de más a menos específico
    3. Primer selector que retorne resultados gana

    IMPORTANTE: Verificar y ajustar selectores contra el DOM real del portal.
    """
    tab_selectors = [
        "a:has-text('Documentos')",
        "a:has-text('Archivos adjuntos')",
        "a:has-text('Archivos')",
        "li:has-text('Documentos') > a",
        "#tabDocumentos a",
        "[id*='TabDocumentos']",
        "[id*='tabDocumentos']",
    ]
    for selector in tab_selectors:
        try:
            el = page.locator(selector).first
            if await el.is_visible(timeout=1500):
                await el.click()
                await page.wait_for_load_state("networkidle", timeout=5000)
                break
        except Exception:  # noqa: S112
            continue

    # Buscar links de descarga — múltiples estrategias, más específico primero
    link_selectors = [
        "a[href*='DownloadFile']",
        "a[href*='GetFile']",
        "a[href*='download']",
        "a[href*='Download']",
        "a[href*='Attachment']",
        "a[href$='.pdf']",
        "a[href$='.doc']",
        "a[href$='.docx']",
        "a[href$='.zip']",
    ]

    seen_urls: set[str] = set()
    adjuntos: list[AdjuntoLicitacion] = []

    for selector in link_selectors:
        elements = page.locator(selector)
        count = await elements.count()

        for i in range(count):
            el = elements.nth(i)
            href = await el.get_attribute("href")
            if not href or href in seen_urls:
                continue

            # Normalizar URL relativa
            if href.startswith("/"):
                href = f"{_PORTAL_BASE}{href}"
            elif not href.startswith("http"):
                continue

            nombre = (await el.inner_text()).strip()
            if not nombre:
                nombre = href.split("/")[-1].split("?")[0] or "documento"

            seen_urls.add(href)
            adjuntos.append(
                AdjuntoLicitacion(
                    nombre=nombre,
                    url_origen=href,
                    tipo=_inferir_tipo(nombre),
                )
            )

        if adjuntos:
            # Primer selector que retornó resultados — no seguir buscando
            break

    return adjuntos


def _inferir_tipo(nombre: str) -> DocumentoTipo:
    """Infiere el tipo de documento por el nombre del archivo o link."""
    n = nombre.lower()
    if re.search(r"administrat|admin", n):
        return DocumentoTipo.bases_administrativas
    if re.search(r"técnic|tecnic|bases.tec", n):
        return DocumentoTipo.bases_tecnicas
    if re.search(r"aclarac", n):
        return DocumentoTipo.aclaracion
    if re.search(r"\brespuesta\b", n):
        return DocumentoTipo.respuesta
    if re.search(r"\bconsulta\b", n):
        return DocumentoTipo.consulta
    if re.search(r"apertura", n):
        return DocumentoTipo.acta_apertura
    if re.search(r"adjudicac", n):
        return DocumentoTipo.acta_adjudicacion
    if re.search(r"\banexo\b", n):
        return DocumentoTipo.anexo
    return DocumentoTipo.otro
