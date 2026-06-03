"""Excepciones del servicio de almacenamiento R2."""


class R2UploadError(Exception):
    """Falló la subida de un archivo a Cloudflare R2."""
