"""Tests unitarios para el helper _add_months de sync_detalle.

Función pura — no requiere base de datos. Cubre desborde de días,
año bisiesto, cruce de año y preservación de hora/timezone.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.tasks.sync_detalle import _add_months


def test_suma_basica_sin_desborde() -> None:
    dt = datetime(2024, 3, 15, tzinfo=UTC)
    assert _add_months(dt, 2) == datetime(2024, 5, 15, tzinfo=UTC)


def test_cruce_de_anio() -> None:
    """Diciembre + 1 mes → enero del año siguiente."""
    dt = datetime(2024, 12, 20, tzinfo=UTC)
    assert _add_months(dt, 1) == datetime(2025, 1, 20, tzinfo=UTC)


def test_doce_meses_mismo_mes_anio_siguiente() -> None:
    dt = datetime(2024, 6, 10, tzinfo=UTC)
    assert _add_months(dt, 12) == datetime(2025, 6, 10, tzinfo=UTC)


def test_24_meses_dos_anios() -> None:
    dt = datetime(2023, 5, 1, tzinfo=UTC)
    assert _add_months(dt, 24) == datetime(2025, 5, 1, tzinfo=UTC)


def test_cero_meses_no_cambia() -> None:
    dt = datetime(2024, 7, 4, tzinfo=UTC)
    assert _add_months(dt, 0) == dt


def test_desborde_enero31_anio_no_bisiesto() -> None:
    """Ene 31 + 1 mes = Feb 28 en año no bisiesto."""
    dt = datetime(2023, 1, 31, tzinfo=UTC)
    assert _add_months(dt, 1) == datetime(2023, 2, 28, tzinfo=UTC)


def test_desborde_enero31_anio_bisiesto() -> None:
    """Ene 31 + 1 mes = Feb 29 en año bisiesto 2024."""
    dt = datetime(2024, 1, 31, tzinfo=UTC)
    assert _add_months(dt, 1) == datetime(2024, 2, 29, tzinfo=UTC)


def test_desborde_marzo31_mas_1() -> None:
    """Mar 31 + 1 mes = Abr 30 (abril tiene 30 días)."""
    dt = datetime(2024, 3, 31, tzinfo=UTC)
    assert _add_months(dt, 1) == datetime(2024, 4, 30, tzinfo=UTC)


def test_desborde_feb29_bisiesto_mas_12() -> None:
    """Feb 29 de año bisiesto + 12 meses = Feb 28 de año no bisiesto."""
    dt = datetime(2024, 2, 29, tzinfo=UTC)
    assert _add_months(dt, 12) == datetime(2025, 2, 28, tzinfo=UTC)


def test_desborde_feb29_bisiesto_mas_48() -> None:
    """Feb 29 bisiesto + 48 meses = Feb 29 del siguiente año bisiesto."""
    dt = datetime(2024, 2, 29, tzinfo=UTC)
    assert _add_months(dt, 48) == datetime(2028, 2, 29, tzinfo=UTC)


def test_preserva_hora_minuto_segundo() -> None:
    dt = datetime(2024, 1, 15, 14, 30, 45, tzinfo=UTC)
    result = _add_months(dt, 3)
    assert result == datetime(2024, 4, 15, 14, 30, 45, tzinfo=UTC)


def test_preserva_timezone() -> None:
    dt = datetime(2024, 1, 10, tzinfo=UTC)
    result = _add_months(dt, 6)
    assert result.tzinfo == UTC


def test_cruce_multianio() -> None:
    """15 meses cruza año y mes."""
    dt = datetime(2024, 10, 5, tzinfo=UTC)
    assert _add_months(dt, 15) == datetime(2026, 1, 5, tzinfo=UTC)
