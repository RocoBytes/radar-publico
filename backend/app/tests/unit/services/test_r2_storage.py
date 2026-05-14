"""Tests unitarios del servicio de almacenamiento R2.

Sin conexión real a R2 — boto3 se mockea con patch.
Casos cubiertos:
- Subida exitosa: retorna StorageResult con todos los campos poblados.
- Archivo demasiado grande: ValueError antes de llamar boto3.
- Error de boto3: R2UploadError propagado correctamente.
"""

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.services.storage.exceptions import R2UploadError
from app.services.storage.r2 import MAX_TAMANO_BYTES, StorageResult, subir_documento

_FAKE_PDF = b"%PDF-1.4 fake content for testing"


@pytest.mark.asyncio
async def test_subir_documento_ok() -> None:
    """Subida exitosa retorna StorageResult con hash, path, bucket y mime."""
    mock_s3 = MagicMock()
    mock_s3.put_object = MagicMock()

    with (
        patch("app.services.storage.r2.boto3.client", return_value=mock_s3),
        patch(
            "app.services.storage.r2.magic.from_buffer",
            return_value="application/pdf",
        ),
    ):
        result = await subir_documento(_FAKE_PDF, "1234-56-LR26")

    assert isinstance(result, StorageResult)
    assert result.storage_path.startswith("bases/1234-56-LR26/")
    assert result.storage_path.endswith(".pdf")
    assert result.storage_bucket == settings.r2_bucket
    assert result.tamano_bytes == len(_FAKE_PDF)
    assert result.mime_type == "application/pdf"
    assert result.hash_sha256 == hashlib.sha256(_FAKE_PDF).hexdigest()
    mock_s3.put_object.assert_called_once()

    call_kwargs = mock_s3.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == settings.r2_bucket
    assert call_kwargs["Key"] == result.storage_path
    assert call_kwargs["ContentType"] == "application/pdf"


@pytest.mark.asyncio
async def test_subir_documento_tamano_excedido() -> None:
    """Archivo mayor a MAX_TAMANO_BYTES lanza ValueError sin llamar boto3."""
    contenido_grande = b"x" * (MAX_TAMANO_BYTES + 1)

    with (
        patch("app.services.storage.r2.boto3.client") as mock_boto,
        patch("app.services.storage.r2.magic.from_buffer", return_value="text/plain"),
        pytest.raises(ValueError, match="tamaño máximo"),
    ):
        await subir_documento(contenido_grande, "1234-56-LR26")

    mock_boto.assert_not_called()


@pytest.mark.asyncio
async def test_subir_documento_r2_error() -> None:
    """ClientError de boto3 se transforma en R2UploadError."""
    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}}
    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = ClientError(error_response, "PutObject")

    with (
        patch("app.services.storage.r2.boto3.client", return_value=mock_s3),
        patch(
            "app.services.storage.r2.magic.from_buffer",
            return_value="application/pdf",
        ),
        pytest.raises(R2UploadError, match="Bucket not found"),
    ):
        await subir_documento(_FAKE_PDF, "1234-56-LR26")


@pytest.mark.asyncio
async def test_subir_documento_sin_extension_conocida() -> None:
    """Mime type desconocido: path sin extensión pero subida exitosa."""
    mock_s3 = MagicMock()
    mock_s3.put_object = MagicMock()

    with (
        patch("app.services.storage.r2.boto3.client", return_value=mock_s3),
        patch(
            "app.services.storage.r2.magic.from_buffer",
            return_value="application/octet-stream",  # sin extensión mapeada
        ),
    ):
        result = await subir_documento(b"raw bytes", "5678-10-LR26")

    # Sin extensión — path termina en el uuid sin extensión
    assert result.storage_path.startswith("bases/5678-10-LR26/")
    assert not result.storage_path.endswith(".pdf")
    mock_s3.put_object.assert_called_once()
