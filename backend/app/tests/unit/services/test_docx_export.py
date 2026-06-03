"""Tests unitarios para app/services/docx_export.py — generar_docx_borrador.

Valida:
- Que el buffer retornado sea un BytesIO no vacío
- Que los primeros 4 bytes sean el magic ZIP/DOCX (b"PK\\x03\\x04")
- Que el título por defecto sea "Propuesta Técnica" cuando titulo=None
- Que el título personalizado aparezca en el documento
- Que las secciones, documentos_pendientes y notas_revision se incluyan
- Que todos los campos None no provoquen error
- Que el buffer esté posicionado en 0 tras save (listo para lectura)

No usa BD, ni AsyncClient, ni fixtures de conftest — es puro test de función.
"""

from __future__ import annotations

import io
from types import SimpleNamespace
from typing import Any

import pytest
from docx import Document as DocxDocument

from app.services.docx_export import generar_docx_borrador


# ---------------------------------------------------------------------------
# Helper: extrae todo el texto del documento como una sola cadena
# ---------------------------------------------------------------------------


def _text_from_buffer(buffer: io.BytesIO) -> str:
    """Lee el buffer DOCX con python-docx y concatena todos los párrafos."""
    buffer.seek(0)
    doc = DocxDocument(buffer)
    return "\n".join(p.text for p in doc.paragraphs)


# ---------------------------------------------------------------------------
# Helper: construye un borrador falso compatible con generar_docx_borrador
# ---------------------------------------------------------------------------


def _borrador(
    titulo: str | None = "Propuesta Test",
    secciones: list[Any] | None = None,
    documentos_pendientes: list[Any] | None = None,
    notas_revision: list[Any] | None = None,
) -> Any:
    return SimpleNamespace(
        titulo=titulo,
        secciones=secciones,
        documentos_pendientes=documentos_pendientes,
        notas_revision=notas_revision,
    )


# ---------------------------------------------------------------------------
# Caso 1: retorna un BytesIO no vacío
# ---------------------------------------------------------------------------


def test_retorna_bytesio_no_vacio() -> None:
    buffer = generar_docx_borrador(_borrador())
    assert isinstance(buffer, io.BytesIO), "Debe retornar un io.BytesIO"
    content = buffer.read()
    assert len(content) > 0, "El buffer no debe estar vacío"


# ---------------------------------------------------------------------------
# Caso 2: magic bytes válidos para ZIP/DOCX
# ---------------------------------------------------------------------------


def test_magic_bytes_son_pk_zip() -> None:
    """Un archivo DOCX es un ZIP — los primeros 4 bytes deben ser b'PK\\x03\\x04'."""
    buffer = generar_docx_borrador(_borrador())
    buffer.seek(0)
    primeros_cuatro = buffer.read(4)
    assert primeros_cuatro == b"PK\x03\x04", (
        f"Magic bytes DOCX esperados b'PK\\x03\\x04', obtenidos: {primeros_cuatro!r}"
    )


# ---------------------------------------------------------------------------
# Caso 3: titulo=None → usa "Propuesta Técnica" (sin crash)
# ---------------------------------------------------------------------------


def test_titulo_none_usa_default() -> None:
    """titulo=None → el documento se genera con 'Propuesta Técnica' como heading."""
    buffer = generar_docx_borrador(_borrador(titulo=None))
    text = _text_from_buffer(buffer)
    assert "Propuesta" in text, (
        f"El documento debe contener 'Propuesta' cuando titulo=None. "
        f"Texto extraído: {text!r}"
    )


# ---------------------------------------------------------------------------
# Caso 4: titulo personalizado aparece en el documento
# ---------------------------------------------------------------------------


def test_titulo_personalizado_aparece_en_docx() -> None:
    titulo = "Mi Propuesta Técnica Personalizada"
    buffer = generar_docx_borrador(_borrador(titulo=titulo))
    text = _text_from_buffer(buffer)
    assert "Mi Propuesta Técnica Personalizada" in text, (
        f"El título personalizado debe aparecer en el DOCX. "
        f"Texto extraído: {text!r}"
    )


# ---------------------------------------------------------------------------
# Caso 5: 2 secciones → ambas aparecen en el documento
# ---------------------------------------------------------------------------


def test_dos_secciones_ambas_en_docx() -> None:
    secciones = [
        {"titulo": "Sección Alfa", "contenido": "Contenido de la sección alfa aquí."},
        {"titulo": "Sección Beta", "contenido": "Contenido de la sección beta aquí."},
    ]
    buffer = generar_docx_borrador(_borrador(secciones=secciones))
    text = _text_from_buffer(buffer)

    assert "Sección Alfa" in text, (
        f"La primera sección debe estar en el DOCX. Texto: {text!r}"
    )
    assert "Sección Beta" in text, (
        f"La segunda sección debe estar en el DOCX. Texto: {text!r}"
    )
    assert "Contenido de la sección alfa" in text, (
        f"El contenido de la primera sección debe estar en el DOCX. Texto: {text!r}"
    )
    assert "Contenido de la sección beta" in text, (
        f"El contenido de la segunda sección debe estar en el DOCX. Texto: {text!r}"
    )


# ---------------------------------------------------------------------------
# Caso 6: documentos_pendientes → ambos aparecen en el DOCX
# ---------------------------------------------------------------------------


def test_documentos_pendientes_aparecen_en_docx() -> None:
    docs = ["Certificado ISO 9001", "Declaración jurada notarial"]
    buffer = generar_docx_borrador(_borrador(documentos_pendientes=docs))
    text = _text_from_buffer(buffer)

    assert "Certificado ISO 9001" in text, (
        f"El primer documento pendiente debe aparecer en el DOCX. Texto: {text!r}"
    )
    assert "Declaración jurada notarial" in text, (
        f"El segundo documento pendiente debe aparecer en el DOCX. Texto: {text!r}"
    )


# ---------------------------------------------------------------------------
# Caso 7: notas_revision → aparece en el DOCX
# ---------------------------------------------------------------------------


def test_notas_revision_aparecen_en_docx() -> None:
    notas = ["Revisar plazos con el equipo legal antes de entregar"]
    buffer = generar_docx_borrador(_borrador(notas_revision=notas))
    text = _text_from_buffer(buffer)

    assert "Revisar plazos" in text, (
        f"La nota de revisión debe aparecer en el DOCX. Texto: {text!r}"
    )


# ---------------------------------------------------------------------------
# Caso 8: todos los campos None → sin crash, DOCX válido
# ---------------------------------------------------------------------------


def test_todos_none_no_falla() -> None:
    """titulo=None, secciones=None, documentos_pendientes=None, notas_revision=None."""
    borrador = _borrador(
        titulo=None,
        secciones=None,
        documentos_pendientes=None,
        notas_revision=None,
    )
    # No debe lanzar ninguna excepción
    buffer = generar_docx_borrador(borrador)
    buffer.seek(0)
    primeros_cuatro = buffer.read(4)
    assert primeros_cuatro == b"PK\x03\x04", (
        "Incluso con todos los campos None, el DOCX debe ser válido"
    )


# ---------------------------------------------------------------------------
# Caso 9: buffer posicionado en 0 tras save (listo para lectura inmediata)
# ---------------------------------------------------------------------------


def test_buffer_posicionado_en_cero_tras_save() -> None:
    """generar_docx_borrador debe hacer buffer.seek(0) antes de retornar."""
    buffer = generar_docx_borrador(_borrador())
    posicion_inicial = buffer.tell()
    assert posicion_inicial == 0, (
        f"El buffer debe estar en posición 0, actual: {posicion_inicial}. "
        "La función debe llamar buffer.seek(0) antes de retornar."
    )

    # Adicionalmente: leer desde esa posición debe producir un ZIP válido
    primeros = buffer.read(4)
    assert primeros == b"PK\x03\x04"
