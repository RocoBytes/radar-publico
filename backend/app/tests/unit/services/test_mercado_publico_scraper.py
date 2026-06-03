"""Tests unitarios del scraper de Mercado Público.

Sin red ni Playwright real — playwright_page se mockea con asynccontextmanager.
Casos cubiertos:
- _inferir_tipo: mapeo de nombres a DocumentoTipo.
- extraer_adjuntos: extracción de links con página HTML mínima.
- Errores: 404, portal bloqueado (403), sin bases (sin links encontrados).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import DocumentoTipo
from app.services.scraping.exceptions import (
    LicitacionSinBasesError,
    PortalBloqueadoError,
    PortalPaginaNoEncontradaError,
)
from app.services.scraping.mercado_publico import _inferir_tipo, extraer_adjuntos

# ---------------------------------------------------------------------------
# Fixture HTML del portal (fixture file en tests/fixtures/portal/)
# ---------------------------------------------------------------------------

_FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "portal"
_SAMPLE_HTML = (_FIXTURE_DIR / "sample_page.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status = status
    return r


def _make_mock_page(
    response_status: int = 200,
    body_text: str = "Página normal",
    links: list[tuple[str, str]] | None = None,
) -> AsyncMock:
    """Crea un mock de Playwright Page para los tests."""
    if links is None:
        links = [
            ("/DownloadFile?id=100", "Bases Administrativas"),
            ("/DownloadFile?id=101", "Bases Técnicas"),
        ]

    page = AsyncMock()

    # goto retorna un response mock
    response_mock = _make_mock_response(response_status)
    page.goto = AsyncMock(return_value=response_mock)
    page.inner_text = AsyncMock(return_value=body_text)
    page.wait_for_load_state = AsyncMock()
    page.set_default_timeout = MagicMock()

    # Simular locator para tab de documentos (invisible → no click)
    tab_locator = AsyncMock()
    tab_locator.is_visible = AsyncMock(return_value=False)
    first_locator = MagicMock()
    first_locator.is_visible = AsyncMock(return_value=False)
    tab_locator.first = first_locator

    # Simular locator para links de descarga
    link_locator = AsyncMock()
    link_locator.count = AsyncMock(return_value=len(links))

    def nth(i: int) -> AsyncMock:
        el = AsyncMock()
        el.get_attribute = AsyncMock(return_value=links[i][0])
        el.inner_text = AsyncMock(return_value=links[i][1])
        return el

    link_locator.nth = nth

    def mock_locator(selector: str) -> AsyncMock:
        if "DownloadFile" in selector or "download" in selector.lower():
            return link_locator
        # Otros selectores retornan sin resultados
        empty = AsyncMock()
        empty.count = AsyncMock(return_value=0)
        empty.first = first_locator
        return empty

    page.locator = mock_locator
    return page


@asynccontextmanager
async def _mock_playwright_page_ctx(page: AsyncMock) -> AsyncIterator[AsyncMock]:
    """Async context manager que inyecta un page mock."""
    yield page


# ---------------------------------------------------------------------------
# Tests de _inferir_tipo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("Bases Administrativas.pdf", DocumentoTipo.bases_administrativas),
        ("bases_admin_v2.docx", DocumentoTipo.bases_administrativas),
        ("Bases Técnicas.pdf", DocumentoTipo.bases_tecnicas),
        ("bases_tecnicas_final.pdf", DocumentoTipo.bases_tecnicas),
        ("Bases Tec v3.pdf", DocumentoTipo.bases_tecnicas),
        ("Anexo 1 - Formulario.pdf", DocumentoTipo.anexo),
        ("Aclaración 3.pdf", DocumentoTipo.aclaracion),
        ("Consulta Proveedor ABC.pdf", DocumentoTipo.consulta),
        ("Respuesta Consulta 5.pdf", DocumentoTipo.respuesta),
        ("Acta de Apertura.pdf", DocumentoTipo.acta_apertura),
        ("Acta Adjudicación Final.pdf", DocumentoTipo.acta_adjudicacion),
        ("documento_sin_clasificar.pdf", DocumentoTipo.otro),
        ("archivo.zip", DocumentoTipo.otro),
    ],
)
def test_inferir_tipo(nombre: str, esperado: DocumentoTipo) -> None:
    assert _inferir_tipo(nombre) == esperado


# ---------------------------------------------------------------------------
# Tests de extraer_adjuntos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extraer_adjuntos_ok() -> None:
    """Página normal con links → retorna lista de AdjuntoLicitacion."""
    mock_page = _make_mock_page()

    with (
        patch(
            "app.services.scraping.mercado_publico.playwright_page",
            return_value=_mock_playwright_page_ctx(mock_page),
        ),
        patch("asyncio.sleep"),  # skip delay anti-bot en tests
    ):
        adjuntos = await extraer_adjuntos("1234-56-LR26")

    assert len(adjuntos) == 2
    nombres = [a.nombre for a in adjuntos]
    assert "Bases Administrativas" in nombres
    assert "Bases Técnicas" in nombres

    tipos = {a.nombre: a.tipo for a in adjuntos}
    assert tipos["Bases Administrativas"] == DocumentoTipo.bases_administrativas
    assert tipos["Bases Técnicas"] == DocumentoTipo.bases_tecnicas

    # URLs normalizadas a absolutas
    for adjunto in adjuntos:
        assert adjunto.url_origen.startswith("https://www.mercadopublico.cl")


@pytest.mark.asyncio
async def test_extraer_adjuntos_404() -> None:
    """Página con status 404 → PortalPaginaNoEncontradaError."""
    mock_page = _make_mock_page(response_status=404)

    with (
        patch(
            "app.services.scraping.mercado_publico.playwright_page",
            return_value=_mock_playwright_page_ctx(mock_page),
        ),
        patch("asyncio.sleep"),
        pytest.raises(PortalPaginaNoEncontradaError),
    ):
        await extraer_adjuntos("NOEXISTE-01-LR26")


@pytest.mark.asyncio
async def test_extraer_adjuntos_bloqueado_403() -> None:
    """Portal responde 403 → PortalBloqueadoError."""
    mock_page = _make_mock_page(response_status=403)

    with (
        patch(
            "app.services.scraping.mercado_publico.playwright_page",
            return_value=_mock_playwright_page_ctx(mock_page),
        ),
        patch("asyncio.sleep"),
        pytest.raises(PortalBloqueadoError),
    ):
        await extraer_adjuntos("1234-56-LR26")


@pytest.mark.asyncio
async def test_extraer_adjuntos_captcha_en_contenido() -> None:
    """Página con texto de captcha → PortalBloqueadoError aunque status sea 200."""
    mock_page = _make_mock_page(body_text="Por favor complete el captcha para continuar")

    with (
        patch(
            "app.services.scraping.mercado_publico.playwright_page",
            return_value=_mock_playwright_page_ctx(mock_page),
        ),
        patch("asyncio.sleep"),
        pytest.raises(PortalBloqueadoError),
    ):
        await extraer_adjuntos("1234-56-LR26")


@pytest.mark.asyncio
async def test_extraer_adjuntos_sin_links() -> None:
    """Página sin links de descarga → LicitacionSinBasesError."""
    mock_page = _make_mock_page(links=[])

    with (
        patch(
            "app.services.scraping.mercado_publico.playwright_page",
            return_value=_mock_playwright_page_ctx(mock_page),
        ),
        patch("asyncio.sleep"),
        pytest.raises(LicitacionSinBasesError),
    ):
        await extraer_adjuntos("1234-56-LR26")
