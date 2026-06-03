"""Tests unitarios de procesar_pdf_documento.

Usan BD de test (NullPool — conftest patch_db_session) y mocks de R2,
parsear_pdf y chunkear_documento.
Sin red, sin R2 real, sin pymupdf real.

Casos cubiertos:
- doc_no_encontrado: documento inexistente → errores=1.
- doc_ya_procesado: status=procesado → sin_cambio=1, sin re-proceso.
- doc_sin_storage_path: storage_path nulo → errores=1.
- procesar_pdf_ok: happy path → procesado=1, chunks creados, send_task encolado.
- procesar_pdf_escaneado: PdfEscaneadoError → errores=1, status='error'.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
import pytest_asyncio

if TYPE_CHECKING:
    from app.services.pdf.chunker import Chunk
    from app.services.pdf.parser import ParsedPdf

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_PDF = b"%PDF-1.4 contenido falso"
_FAKE_STORAGE_PATH = "bases/TEST/doc.pdf"


def _make_parsed_pdf(num_paginas: int = 2) -> "ParsedPdf":
    from app.services.pdf.parser import ParsedPdf

    return ParsedPdf(
        paginas=["Página uno con texto suficiente.", "Página dos con más texto."],
        num_paginas=num_paginas,
        hash_contenido="aabbcc" + "00" * 29,
    )


def _make_chunks(n: int = 2) -> "list[Chunk]":
    from app.services.pdf.chunker import Chunk

    return [
        Chunk(
            orden=i,
            contenido=f"Chunk {i} de prueba",
            pagina_inicio=i,
            pagina_fin=i,
            tokens=10,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Fixture: licitación + documento con status=descargado
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def documento_descargado() -> dict[str, str]:  # type: ignore[misc]
    """Crea licitación y DocumentoBase con status=descargado en la BD de test."""
    from app.db.session import AsyncSessionLocal
    from app.models.documento_base import DocumentoBase
    from app.models.enums import DocumentoStatus, DocumentoTipo, LicitacionEstado
    from app.models.licitacion import Licitacion

    codigo_lic = f"PDF-{uuid.uuid4().hex[:6]}-L26"
    doc_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        lic = Licitacion(
            codigo=codigo_lic,
            nombre="Licitación para test PDF",
            estado=LicitacionEstado.publicada,
            estado_codigo=5,
            detalle_sincronizado_at=datetime.now(UTC),
        )
        session.add(lic)
        await session.flush()

        doc = DocumentoBase(
            id=doc_id,
            licitacion_codigo=codigo_lic,
            tipo=DocumentoTipo.bases_administrativas,
            status=DocumentoStatus.descargado,
            storage_path=_FAKE_STORAGE_PATH,
            storage_bucket="radar-publico-dev",
            descargado_at=datetime.now(UTC),
        )
        session.add(doc)
        await session.commit()

    yield {"documento_id": str(doc_id), "licitacion_codigo": codigo_lic}

    async with AsyncSessionLocal() as session:
        lic_obj = await session.get(Licitacion, codigo_lic)
        if lic_obj:
            await session.delete(lic_obj)
            await session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_doc_no_encontrado() -> None:
    """UUID inexistente en la BD → errores=1, sin excepción."""
    from app.tasks.procesar_pdf import _run

    doc_id = str(uuid.uuid4())
    result = await _run(doc_id)

    assert result["errores"] == 1, f"Esperado errores=1, got: {result}"
    assert result["procesado"] == 0
    assert result["sin_cambio"] == 0


@pytest.mark.asyncio
async def test_doc_ya_procesado(documento_descargado: dict[str, str]) -> None:
    """Documento con status=procesado → sin_cambio=1, sin re-proceso."""
    from app.db.session import AsyncSessionLocal
    from app.models.documento_base import DocumentoBase
    from app.models.enums import DocumentoStatus
    from app.tasks.procesar_pdf import _run

    doc_id = documento_descargado["documento_id"]

    # Marcar como procesado
    async with AsyncSessionLocal() as session:
        doc = await session.get(DocumentoBase, uuid.UUID(doc_id))
        assert doc is not None
        doc.status = DocumentoStatus.procesado
        await session.commit()

    mock_descargar = AsyncMock()

    with patch("app.services.storage.r2.descargar_documento", mock_descargar):
        result = await _run(doc_id)

    assert result["sin_cambio"] == 1, f"Esperado sin_cambio=1, got: {result}"
    assert result["procesado"] == 0
    mock_descargar.assert_not_called()


@pytest.mark.asyncio
async def test_doc_sin_storage_path(documento_descargado: dict[str, str]) -> None:
    """storage_path=None → errores=1, sin descarga."""
    from app.db.session import AsyncSessionLocal
    from app.models.documento_base import DocumentoBase
    from app.tasks.procesar_pdf import _run

    doc_id = documento_descargado["documento_id"]

    async with AsyncSessionLocal() as session:
        doc = await session.get(DocumentoBase, uuid.UUID(doc_id))
        assert doc is not None
        doc.storage_path = None
        await session.commit()

    mock_descargar = AsyncMock()

    with patch("app.services.storage.r2.descargar_documento", mock_descargar):
        result = await _run(doc_id)

    assert result["errores"] == 1, f"Esperado errores=1, got: {result}"
    mock_descargar.assert_not_called()


@pytest.mark.asyncio
async def test_procesar_pdf_ok(documento_descargado: dict[str, str]) -> None:
    """Happy path: descarga, parsea, chunkea, persiste y encola embed_chunks."""
    from sqlalchemy import func, select

    from app.db.session import AsyncSessionLocal
    from app.models.documento_base import DocumentoBase, DocumentoChunk
    from app.models.enums import DocumentoStatus
    from app.tasks.procesar_pdf import _run

    doc_id = documento_descargado["documento_id"]
    parsed = _make_parsed_pdf()
    chunks = _make_chunks(3)

    with (
        patch(
            "app.services.storage.r2.descargar_documento",
            AsyncMock(return_value=_FAKE_PDF),
        ),
        patch(
            "app.services.pdf.parser.parsear_pdf",
            AsyncMock(return_value=parsed),
        ),
        patch(
            "app.services.pdf.chunker.chunkear_documento",
            return_value=chunks,
        ),
        patch("app.celery_app.celery_app.send_task") as mock_send,
    ):
        result = await _run(doc_id)

    assert result["procesado"] == 1, f"Esperado procesado=1, got: {result}"
    assert result["chunks_creados"] == 3
    assert result["errores"] == 0

    # Verificar estado en BD
    async with AsyncSessionLocal() as session:
        doc = await session.get(DocumentoBase, uuid.UUID(doc_id))
        assert doc is not None
        assert doc.status == DocumentoStatus.procesado
        assert doc.procesado_at is not None
        assert doc.num_paginas == parsed.num_paginas

        count = (
            await session.execute(
                select(func.count()).where(
                    DocumentoChunk.documento_id == uuid.UUID(doc_id)
                )
            )
        ).scalar()
        assert count == 3, f"Esperados 3 chunks, got {count}"

    # Verificar que encoló embed_chunks
    mock_send.assert_called_once_with(
        "tasks.embed_chunks.embed_chunks_documento",
        args=[doc_id],
    )


@pytest.mark.asyncio
async def test_procesar_pdf_escaneado(documento_descargado: dict[str, str]) -> None:
    """PdfEscaneadoError → errores=1, status seteado a 'error'."""
    from app.db.session import AsyncSessionLocal
    from app.models.documento_base import DocumentoBase
    from app.models.enums import DocumentoStatus
    from app.services.pdf.exceptions import PdfEscaneadoError
    from app.tasks.procesar_pdf import _run

    doc_id = documento_descargado["documento_id"]

    with (
        patch(
            "app.services.storage.r2.descargar_documento",
            AsyncMock(return_value=_FAKE_PDF),
        ),
        patch(
            "app.services.pdf.parser.parsear_pdf",
            AsyncMock(side_effect=PdfEscaneadoError("PDF escaneado sin OCR")),
        ),
    ):
        result = await _run(doc_id)

    assert result["errores"] == 1, f"Esperado errores=1, got: {result}"
    assert result["procesado"] == 0

    async with AsyncSessionLocal() as session:
        doc = await session.get(DocumentoBase, uuid.UUID(doc_id))
        assert doc is not None
        assert doc.status == DocumentoStatus.error
        assert doc.error_mensaje is not None
