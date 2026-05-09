"""Tests unitarios para app.services.chilecompra.utils.

Casos edge documentados en CLAUDE.md §9:
- Formato ddmmaaaa sin separadores (trampa #1).
- Cambio de mes, año bisiesto, fechas límite.
- Validación de códigos de licitación.
- Parse de fechas ISO de la API.
"""

from datetime import date, datetime

import pytest

from app.services.chilecompra.utils import (
    format_fecha_api,
    parse_fecha_iso,
    validar_codigo_licitacion,
)


class TestFormatFechaApi:
    """CLAUDE.md §9: trampa #1 — formato ddmmaaaa sin separadores."""

    def test_formato_basico(self) -> None:
        assert format_fecha_api(date(2026, 5, 7)) == "07052026"

    def test_dia_y_mes_con_cero_a_la_izquierda(self) -> None:
        assert format_fecha_api(date(2026, 1, 1)) == "01012026"

    def test_ultimo_dia_del_ano(self) -> None:
        assert format_fecha_api(date(2026, 12, 31)) == "31122026"

    def test_cambio_de_mes(self) -> None:
        assert format_fecha_api(date(2026, 3, 31)) == "31032026"
        assert format_fecha_api(date(2026, 4, 1)) == "01042026"

    def test_año_bisiesto_feb_29(self) -> None:
        assert format_fecha_api(date(2024, 2, 29)) == "29022024"

    def test_acepta_datetime(self) -> None:
        """Debe aceptar datetime además de date."""
        dt = datetime(2026, 5, 9, 19, 56, 10)
        assert format_fecha_api(dt) == "09052026"

    def test_ejemplo_documentado_en_claude_md(self) -> None:
        """Ejemplo literal del CLAUDE.md §9."""
        assert format_fecha_api(date(2026, 5, 7)) == "07052026"


class TestParseFechaIso:
    """La API devuelve fechas ISO sin timezone — se tratan como UTC."""

    def test_formato_sin_microsegundos(self) -> None:
        dt = parse_fecha_iso("2026-05-18T15:10:00")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 5
        assert dt.day == 18
        assert dt.hour == 15

    def test_formato_con_microsegundos(self) -> None:
        dt = parse_fecha_iso("2026-04-28T17:53:29.51")
        assert dt is not None
        assert dt.year == 2026
        assert dt.day == 28

    def test_none_devuelve_none(self) -> None:
        assert parse_fecha_iso(None) is None

    def test_string_vacio_devuelve_none(self) -> None:
        assert parse_fecha_iso("") is None

    def test_formato_invalido_devuelve_none(self) -> None:
        assert parse_fecha_iso("no-es-una-fecha") is None

    def test_resultado_tiene_timezone(self) -> None:
        dt = parse_fecha_iso("2026-05-18T15:10:00")
        assert dt is not None
        assert dt.tzinfo is not None


class TestValidarCodigoLicitacion:
    """Validación del formato de código de licitación."""

    @pytest.mark.parametrize(
        "codigo",
        [
            "1000-8-LE26",
            "1003473-14-LR26",
            "1509-5-L114",
            "1002588-59-LE26",
            "1002592-2-LP26",
        ],
    )
    def test_codigos_validos(self, codigo: str) -> None:
        assert validar_codigo_licitacion(codigo) is True

    @pytest.mark.parametrize(
        "codigo",
        [
            "",
            "sin-guiones",
            "1000-8",  # falta tipo
            "LE26-8-1000",  # orden incorrecto
            "1000-8-",  # tipo vacío
        ],
    )
    def test_codigos_invalidos(self, codigo: str) -> None:
        assert validar_codigo_licitacion(codigo) is False
