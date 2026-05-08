"""Configuración global de pytest.

Fixtures compartidas entre tests unitarios e integración.
Se completa en Sprint 1 cuando haya modelos y endpoints reales.
"""

import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Usa asyncio como backend para tests async."""
    return "asyncio"
