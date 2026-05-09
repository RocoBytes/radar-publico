"""Configuración global de pytest.

Fixtures compartidas entre tests unitarios e integración.
"""

from unittest.mock import patch

import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Usa asyncio como backend para tests async."""
    return "asyncio"


@pytest.fixture(autouse=True)
def encryption_key_valida(request: pytest.FixtureRequest) -> None:  # type: ignore[return]
    """Garantiza que ENCRYPTION_KEY tiene 32 bytes en todos los tests.

    Los tests que mockean settings explícitamente no se ven afectados
    porque el mock de la función individual tiene precedencia.
    """
    # Solo aplicar en tests de cifrado para no interferir con otros
    if "test_encryption" not in request.node.nodeid:
        yield  # type: ignore[misc]
        return

    with patch("app.core.encryption.settings") as mock_settings:
        mock_settings.encryption_key = "A" * 32  # clave válida de 32 bytes
        yield  # type: ignore[misc]
