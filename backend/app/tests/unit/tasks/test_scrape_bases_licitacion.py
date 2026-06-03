"""Tests unitarios de scrape_bases_licitacion.

Usan BD de test (NullPool — conftest patch_db_session) y mocks del scraper y R2.
Sin red, sin Playwright real, sin R2 real.

Casos cubiertos:
- Nueva descarga: crea filas en documentos_bases, setea bases_descargadas_at.
- Idempotencia: segunda ejecución retorna sin_cambio=1 (bases_descargadas_at poblado).
- Sin bases: LicitacionSinBasesError → sin_bases=1, bases_descargadas_at seteado.
- No encontrada: PortalPaginaNoEncontradaError → no_encontrada=1.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
import pytest_asyncio

if TYPE_CHECKING:
    from app.services.storage.r2 import StorageResult

from app.services.scraping.exceptions import (
    LicitacionSinBasesError,
    PortalPaginaNoEncontradaError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_PDF = b"%PDF-1.4 fake content"
_FAKE_HASH = "aabbccdd" + "00" * 28  # 64 hex chars


def _make_adjunto(nombre: str = "Bases Administrativas.pdf") -> MagicMock:
    from app.models.enums import DocumentoTipo

    adj = MagicMock()
    adj.nombre = nombre
    adj.url_origen = "https://www.mercadopublico.cl/DownloadFile?id=1"
    adj.tipo = DocumentoTipo.bases_administrativas
    return adj


def _make_storage_result(storage_path: str = "bases/TEST/uuid.pdf") -> StorageResult:
    from app.services.storage.r2 import StorageResult

    return StorageResult(
        storage_path=storage_path,
        storage_bucket="radar-publico-dev",
        tamano_bytes=len(_FAKE_PDF),
        hash_sha256=_FAKE_HASH,
        mime_type="application/pdf",
    )


# ---------------------------------------------------------------------------
# Fixture: licitación con detalle ya sincronizado
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def licitacion_existente() -> dict[str, str]:  # type: ignore[misc]
    """Crea una licitación con detalle_sincronizado_at en la BD de test."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import LicitacionEstado
    from app.models.licitacion import Licitacion

    codigo = f"BASE-{uuid.uuid4().hex[:6]}-L26"

    async with AsyncSessionLocal() as session:
        lic = Licitacion(
            codigo=codigo,
            nombre="Licitación para test de scraping",
            estado=LicitacionEstado.publicada,
            estado_codigo=5,
            detalle_sincronizado_at=datetime.now(UTC),
        )
        session.add(lic)
        await session.commit()

    yield {"codigo": codigo}

    async with AsyncSessionLocal() as session:
        lic_cleanup = await session.get(Licitacion, codigo)
        if lic_cleanup:
            await session.delete(lic_cleanup)
            await session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scrape_bases_nueva(licitacion_existente: dict[str, str]) -> None:
    """Descarga exitosa: crea fila en documentos_bases y setea bases_descargadas_at."""
    from sqlalchemy import func, select

    from app.db.session import AsyncSessionLocal
    from app.models.documento_base import DocumentoBase
    from app.models.licitacion import Licitacion
    from app.tasks.scrape_bases import _run

    codigo = licitacion_existente["codigo"]
    adjunto = _make_adjunto()
    resultado_r2 = _make_storage_result(f"bases/{codigo}/{uuid.uuid4()}.pdf")

    mock_http = AsyncMock()
    mock_response = AsyncMock()
    mock_response.content = _FAKE_PDF
    mock_response.raise_for_status = MagicMock()
    mock_http.get = AsyncMock(return_value=mock_response)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.scraping.mercado_publico.extraer_adjuntos",
            AsyncMock(return_value=[adjunto]),
        ),
        patch(
            "app.services.storage.r2.subir_documento",
            AsyncMock(return_value=resultado_r2),
        ),
        patch("httpx.AsyncClient", return_value=mock_http),
    ):
        result = await _run(codigo)

    assert result["descargados"] == 1, f"Esperado 1 descargado, got: {result}"
    assert result["errores"] == 0
    assert result["sin_cambio"] == 0

    async with AsyncSessionLocal() as session:
        count = (
            await session.execute(
                select(func.count()).where(DocumentoBase.licitacion_codigo == codigo)
            )
        ).scalar()
        assert count == 1, f"Esperada 1 fila en documentos_bases, got {count}"

        lic = await session.get(Licitacion, codigo)
        assert lic is not None
        assert lic.bases_descargadas_at is not None, "bases_descargadas_at debe estar seteado"


@pytest.mark.asyncio
async def test_scrape_bases_idempotente(licitacion_existente: dict[str, str]) -> None:
    """Segunda ejecución retorna sin_cambio=1 sin re-scrape ni re-subida."""
    from app.db.session import AsyncSessionLocal
    from app.models.licitacion import Licitacion
    from app.tasks.scrape_bases import _run

    codigo = licitacion_existente["codigo"]

    # Marcar bases_descargadas_at manualmente — simula primera corrida completada
    async with AsyncSessionLocal() as session:
        lic = await session.get(Licitacion, codigo)
        assert lic is not None
        lic.bases_descargadas_at = datetime.now(UTC)
        await session.commit()

    mock_extraer = AsyncMock()

    with patch("app.services.scraping.mercado_publico.extraer_adjuntos", mock_extraer):
        result = await _run(codigo)

    assert result["sin_cambio"] == 1, f"Esperado sin_cambio=1, got: {result}"
    # El scraper no debe haberse llamado
    mock_extraer.assert_not_called()


@pytest.mark.asyncio
async def test_scrape_bases_sin_bases(licitacion_existente: dict[str, str]) -> None:
    """Sin adjuntos: sin_bases=1 y bases_descargadas_at seteado igualmente."""
    from app.db.session import AsyncSessionLocal
    from app.models.licitacion import Licitacion
    from app.tasks.scrape_bases import _run

    codigo = licitacion_existente["codigo"]

    with patch(
        "app.services.scraping.mercado_publico.extraer_adjuntos",
        AsyncMock(side_effect=LicitacionSinBasesError(codigo)),
    ):
        result = await _run(codigo)

    assert result["sin_bases"] == 1, f"Esperado sin_bases=1, got: {result}"
    assert result["errores"] == 0

    async with AsyncSessionLocal() as session:
        lic = await session.get(Licitacion, codigo)
        assert lic is not None
        assert (
            lic.bases_descargadas_at is not None
        ), "bases_descargadas_at debe setearse incluso sin documentos"


@pytest.mark.asyncio
async def test_scrape_bases_no_encontrada(licitacion_existente: dict[str, str]) -> None:
    """Página 404 en el portal: no_encontrada=1, bases_descargadas_at permanece nulo."""
    from app.db.session import AsyncSessionLocal
    from app.models.licitacion import Licitacion
    from app.tasks.scrape_bases import _run

    codigo = licitacion_existente["codigo"]

    with patch(
        "app.services.scraping.mercado_publico.extraer_adjuntos",
        AsyncMock(side_effect=PortalPaginaNoEncontradaError(codigo)),
    ):
        result = await _run(codigo)

    assert result["no_encontrada"] == 1, f"Esperado no_encontrada=1, got: {result}"
    assert result["errores"] == 0

    async with AsyncSessionLocal() as session:
        lic = await session.get(Licitacion, codigo)
        assert lic is not None
        assert lic.bases_descargadas_at is None, "bases_descargadas_at no debe setearse en 404"


@pytest.mark.asyncio
async def test_scrape_bases_idempotencia_nivel_documento(
    licitacion_existente: dict[str, str],
) -> None:
    """Documento con hash ya existente: se saltea sin duplicar fila."""
    import hashlib

    from sqlalchemy import func, select

    from app.db.session import AsyncSessionLocal
    from app.models.documento_base import DocumentoBase
    from app.models.enums import DocumentoStatus
    from app.tasks.scrape_bases import _run

    codigo = licitacion_existente["codigo"]
    hash_real = hashlib.sha256(_FAKE_PDF).hexdigest()

    # Insertar fila preexistente con el mismo hash
    from app.models.enums import DocumentoTipo

    async with AsyncSessionLocal() as session:
        doc_existente = DocumentoBase(
            licitacion_codigo=codigo,
            tipo=DocumentoTipo.bases_administrativas,
            hash_contenido=hash_real,
            status=DocumentoStatus.descargado,
            descargado_at=datetime.now(UTC),
        )
        session.add(doc_existente)
        await session.commit()

    adjunto = _make_adjunto()
    resultado_r2 = _make_storage_result(f"bases/{codigo}/{uuid.uuid4()}.pdf")

    mock_http = AsyncMock()
    mock_response = AsyncMock()
    mock_response.content = _FAKE_PDF
    mock_response.raise_for_status = MagicMock()
    mock_http.get = AsyncMock(return_value=mock_response)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)

    mock_subir = AsyncMock(return_value=resultado_r2)

    with (
        patch(
            "app.services.scraping.mercado_publico.extraer_adjuntos",
            AsyncMock(return_value=[adjunto]),
        ),
        patch("app.services.storage.r2.subir_documento", mock_subir),
        patch("httpx.AsyncClient", return_value=mock_http),
    ):
        result = await _run(codigo)

    # Sin_cambio en nivel documento — no subió nada nuevo
    assert result["sin_cambio"] == 1, f"Esperado sin_cambio=1, got: {result}"
    assert result["descargados"] == 0
    mock_subir.assert_not_called()

    # Solo debe existir 1 fila (la preexistente)
    async with AsyncSessionLocal() as session:
        count = (
            await session.execute(
                select(func.count()).where(DocumentoBase.licitacion_codigo == codigo)
            )
        ).scalar()
        assert count == 1, f"No debe duplicar: esperada 1 fila, got {count}"
