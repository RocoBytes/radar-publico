"""Servicio de almacenamiento de archivos en Cloudflare R2 (compatible S3).

Usa boto3 (síncrono) envuelto en asyncio.to_thread para no bloquear
el event loop. El cliente se crea por llamada — boto3 no es thread-safe
si se reutiliza entre threads concurrentes.

Las URLs de archivos NO se generan aquí — todo acceso a documentos pasa
por el endpoint backend autenticado (regla de oro #10).
"""

import asyncio
from dataclasses import dataclass
import hashlib
import io
import uuid

import boto3
from botocore.exceptions import ClientError
import magic

from app.config import settings
from app.services.storage.exceptions import R2UploadError

# Tamaño máximo permitido antes de rechazar la subida
MAX_TAMANO_BYTES = 50 * 1024 * 1024  # 50 MB

_MIME_EXTENSION: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
    "text/plain": ".txt",
}


@dataclass(frozen=True)
class StorageResult:
    """Resultado de una subida exitosa a R2."""

    storage_path: str
    storage_bucket: str
    tamano_bytes: int
    hash_sha256: str
    mime_type: str


def _extension_para_mime(mime_type: str) -> str:
    return _MIME_EXTENSION.get(mime_type, "")


def _subir_sync(
    contenido: bytes,
    licitacion_codigo: str,
    mime_type: str,
) -> StorageResult:
    """Subida síncrona a R2 — se ejecuta en thread pool vía asyncio.to_thread."""
    extension = _extension_para_mime(mime_type)
    path = f"bases/{licitacion_codigo}/{uuid.uuid4()}{extension}"

    # Cliente boto3 creado por llamada: no es thread-safe si se reutiliza
    client = boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key,
        aws_secret_access_key=settings.r2_secret_key,
        region_name="auto",
    )

    try:
        client.put_object(
            Bucket=settings.r2_bucket,
            Key=path,
            Body=io.BytesIO(contenido),
            ContentType=mime_type,
        )
    except ClientError as exc:
        error_msg = exc.response.get("Error", {}).get("Message", str(exc))
        raise R2UploadError(f"Error subiendo a R2 ({path!r}): {error_msg}") from exc

    return StorageResult(
        storage_path=path,
        storage_bucket=settings.r2_bucket,
        tamano_bytes=len(contenido),
        hash_sha256=hashlib.sha256(contenido).hexdigest(),
        mime_type=mime_type,
    )


def _descargar_sync(path: str, bucket: str) -> bytes:
    """Descarga síncrona desde R2 — se ejecuta en thread pool vía asyncio.to_thread."""
    client = boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key,
        aws_secret_access_key=settings.r2_secret_key,
        region_name="auto",
    )
    try:
        response = client.get_object(Bucket=bucket, Key=path)
        return response["Body"].read()  # type: ignore[no-any-return]
    except ClientError as exc:
        error_msg = exc.response.get("Error", {}).get("Message", str(exc))
        raise R2UploadError(f"Error descargando de R2 ({path!r}): {error_msg}") from exc


async def descargar_documento(path: str, bucket: str) -> bytes:
    """Descarga un documento desde R2 y retorna sus bytes.

    Args:
        path: Ruta del objeto en R2 (ej: 'bases/1234-56-LR26/uuid.pdf').
        bucket: Nombre del bucket.

    Returns:
        Bytes del archivo.

    Raises:
        R2UploadError: Si boto3 falla al descargar.
    """
    return await asyncio.to_thread(_descargar_sync, path, bucket)


async def subir_documento(
    contenido: bytes,
    licitacion_codigo: str,
) -> StorageResult:
    """Sube un documento a R2 y retorna su metadata.

    Detecta el mime_type real con python-magic (no confiar en la extensión
    del nombre del archivo — regla de oro #10 / defensa en profundidad).

    Args:
        contenido: Bytes del archivo descargado.
        licitacion_codigo: Código de la licitación, usado en el path.

    Returns:
        StorageResult con path, bucket, tamaño, hash SHA-256 y mime_type.

    Raises:
        R2UploadError: Si boto3 falla al subir.
        ValueError: Si el archivo supera MAX_TAMANO_BYTES.
    """
    if len(contenido) > MAX_TAMANO_BYTES:
        raise ValueError(
            f"Archivo supera tamaño máximo " f"({len(contenido)} > {MAX_TAMANO_BYTES} bytes)"
        )

    # Detección real del tipo MIME — no confiar en extensión del nombre
    mime_type = magic.from_buffer(contenido[:4096], mime=True)

    return await asyncio.to_thread(_subir_sync, contenido, licitacion_codigo, mime_type)
