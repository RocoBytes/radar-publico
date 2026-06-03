"""Tests unitarios para app.services.pdf.parser."""

from unittest.mock import patch

import fitz  # type: ignore[import-untyped]
import pytest

from app.services.pdf.exceptions import PdfCorruptoError, PdfEscaneadoError
from app.services.pdf.parser import ParsedPdf, parsear_pdf


def _crear_pdf_bytes(textos: list[str] | None = None) -> bytes:
    """Crea un PDF mínimo válido con las páginas indicadas.

    Args:
        textos: Texto a insertar en cada página.
                Si es None se crea un PDF con una página que dice 'Hola mundo test'.

    Returns:
        Bytes del PDF generado.
    """
    if textos is None:
        textos = ["Hola mundo test"]

    doc = fitz.open()
    for texto in textos:
        page = doc.new_page()
        if texto.strip():
            page.insert_text((50, 100), texto)
    return bytes(doc.write())


def _crear_pdf_sin_texto(num_paginas: int = 2) -> bytes:
    """Crea un PDF con páginas en blanco (sin texto extraíble)."""
    doc = fitz.open()
    for _ in range(num_paginas):
        doc.new_page()
    return bytes(doc.write())


# ---------------------------------------------------------------------------
# Fixture: mock asyncio.to_thread para que ejecute la función sincrónicamente
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_to_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hace que asyncio.to_thread ejecute la función directamente (sin thread)."""

    async def _fake_to_thread(func, *args, **kwargs):  # type: ignore[no-untyped-def]
        return func(*args, **kwargs)

    monkeypatch.setattr("app.services.pdf.parser.asyncio.to_thread", _fake_to_thread)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parsear_pdf_valido() -> None:
    """Debe parsear un PDF con texto y retornar ParsedPdf correctamente poblado."""
    texto = "Texto de prueba con suficiente contenido para pasar la heurística."
    pdf_bytes = _crear_pdf_bytes([texto])

    resultado = await parsear_pdf(pdf_bytes)

    assert isinstance(resultado, ParsedPdf)
    assert resultado.num_paginas == 1
    assert len(resultado.paginas) == 1
    assert "Texto de prueba" in resultado.paginas[0]
    assert len(resultado.hash_contenido) == 64  # SHA-256 hex = 64 chars


@pytest.mark.asyncio
async def test_parsear_pdf_corrupto() -> None:
    """Debe lanzar PdfCorruptoError para datos que no son un PDF."""
    contenido_invalido = b"esto no es un pdf"

    with pytest.raises(PdfCorruptoError):
        await parsear_pdf(contenido_invalido)


@pytest.mark.asyncio
async def test_parsear_pdf_mime_incorrecto() -> None:
    """Debe lanzar PdfCorruptoError cuando el MIME no es application/pdf."""
    # Cabecera PNG válida — magic lo detecta como image/png
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
        b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    with pytest.raises(PdfCorruptoError):
        await parsear_pdf(png_bytes)


@pytest.mark.asyncio
async def test_parsear_pdf_escaneado() -> None:
    """Debe lanzar PdfEscaneadoError cuando el PDF no tiene texto extraíble."""
    pdf_sin_texto = _crear_pdf_sin_texto(num_paginas=2)

    # Mockear partition_pdf para simular que unstructured tampoco extrae nada
    with (
        patch(
            "app.services.pdf.parser._extraer_con_unstructured",
            return_value=[],
        ),
        pytest.raises(PdfEscaneadoError),
    ):
        await parsear_pdf(pdf_sin_texto)


@pytest.mark.asyncio
async def test_parsear_pdf_multiples_paginas() -> None:
    """Debe retornar tantas páginas como tenga el PDF."""
    textos = [
        "Primera página con contenido suficiente para pasar la heurística.",
        "Segunda página también con texto de prueba.",
        "Tercera página con más texto de ejemplo.",
    ]
    pdf_bytes = _crear_pdf_bytes(textos)

    resultado = await parsear_pdf(pdf_bytes)

    assert resultado.num_paginas == 3
    assert len(resultado.paginas) == 3


@pytest.mark.asyncio
async def test_parsear_pdf_hash_estable() -> None:
    """El mismo PDF debe producir siempre el mismo hash."""
    texto = "Texto estable con longitud suficiente para no activar la heurística."
    pdf_bytes = _crear_pdf_bytes([texto])

    r1 = await parsear_pdf(pdf_bytes)
    r2 = await parsear_pdf(pdf_bytes)

    assert r1.hash_contenido == r2.hash_contenido
