"""Utilidades para la API de Mercado Público.

CLAUDE.md §9 — trampa #1: formato de fecha ddmmaaaa sin separadores.
Usar SIEMPRE format_fecha_api() para construir fechas en queries.
"""

from datetime import date, datetime
import re


def format_fecha_api(fecha: date | datetime) -> str:
    """Convierte una fecha al formato ddmmaaaa requerido por la API ChileCompra.

    CLAUDE.md §9: "No olvidar fecha en formato ddmmaaaa sin separadores.
    Es la trampa #1."

    Args:
        fecha: Fecha a convertir (date o datetime).

    Returns:
        String en formato ddmmaaaa, ej: "07052026" para 7 de mayo de 2026.

    Examples:
        >>> format_fecha_api(date(2026, 5, 7))
        '07052026'
        >>> format_fecha_api(date(2026, 12, 31))
        '31122026'
    """
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    return fecha.strftime("%d%m%Y")


def parse_fecha_iso(fecha_str: str | None) -> datetime | None:
    """Parsea fechas de las respuestas de la API (ISO 8601 sin timezone).

    La API devuelve fechas sin timezone explícita. Las tratamos como UTC
    para almacenar en BD con timestamptz.

    Args:
        fecha_str: String de fecha de la API, ej: "2026-05-18T15:10:00"
            o "2026-04-28T17:53:29.51". Puede ser None.

    Returns:
        datetime con tzinfo=UTC, o None si el input es None o inválido.
    """
    if not fecha_str:
        return None

    import pytz

    utc = pytz.UTC

    # Intentar varios formatos que devuelve la API
    formatos = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ]
    for fmt in formatos:
        try:
            dt = datetime.strptime(fecha_str, fmt)
            return utc.localize(dt)
        except ValueError:
            continue

    return None


# Regex para validar códigos de licitación
# Formato: {organismo}-{numero}-{tipo}{sufijo}
# Ejemplos: "1000-8-LE26", "1003473-14-LR26", "1509-5-L114"
# El sufijo puede ser 2+ dígitos (no solo año de 2 chars)
_CODIGO_LICITACION_RE = re.compile(r"^\d+-\d+-[A-Z]{1,2}\d+$", re.IGNORECASE)


def validar_codigo_licitacion(codigo: str) -> bool:
    """Valida que un código de licitación tiene el formato correcto.

    Formato: {organismo}-{numero}-{tipo}{año}
    Ejemplos válidos: "1000-8-LE26", "1003473-14-LR26", "1509-5-L114"

    Args:
        codigo: Código a validar.

    Returns:
        True si el formato es válido.
    """
    return bool(_CODIGO_LICITACION_RE.match(codigo.strip()))
