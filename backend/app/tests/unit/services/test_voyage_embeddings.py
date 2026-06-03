"""Tests unitarios para el cliente de embeddings Voyage AI.

Casos cubiertos:
- Happy path: retorno de embeddings de dimensión 1024.
- Lista vacía: retorna lista vacía sin llamar a la API.
- División en sub-batches: 300 textos con batch_size=128 → 3 llamadas.
- Error genérico: se wrappea como EmbeddingError.
- Rate limit: se wrappea como EmbeddingRateLimitError (no se reintenta).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm.exceptions import EmbeddingError, EmbeddingRateLimitError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_voyage_result(num_textos: int) -> MagicMock:
    """Construye un objeto resultado falso de voyageai con embeddings 1024-dim."""
    result = MagicMock()
    result.embeddings = [[0.1] * 1024 for _ in range(num_textos)]
    return result


def _make_mock_client(num_textos: int) -> AsyncMock:
    """Construye un AsyncClient mock que retorna embeddings correctos."""
    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(return_value=_mock_voyage_result(num_textos))
    return mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_batch_basico() -> None:
    """Retorna un vector por texto con dimensión 1024."""
    textos = ["licitación de obras viales", "contrato de suministros"]
    mock_client = _make_mock_client(len(textos))

    with patch("app.services.llm.voyage.voyageai") as mock_voyage:
        mock_voyage.AsyncClient.return_value = mock_client
        # Reimportar la función para que use el mock (evita cache de tenacity)
        from app.services.llm.voyage import embed_batch

        resultado = await embed_batch(textos)

    assert len(resultado) == 2
    assert len(resultado[0]) == 1024
    assert len(resultado[1]) == 1024
    mock_client.embed.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_batch_vacio() -> None:
    """Lista vacía retorna lista vacía sin llamar a la API."""
    with patch("app.services.llm.voyage.voyageai") as mock_voyage:
        mock_client = AsyncMock()
        mock_voyage.AsyncClient.return_value = mock_client

        from app.services.llm.voyage import embed_batch

        resultado = await embed_batch([])

    assert resultado == []
    mock_client.embed.assert_not_awaited()


@pytest.mark.asyncio
async def test_embed_batch_divide_sub_batches() -> None:
    """300 textos con batch_size=128 provoca exactamente 3 llamadas a la API."""
    num_textos = 300
    textos = [f"texto {i}" for i in range(num_textos)]

    # Cada llamada retorna un número variable de embeddings según el batch
    call_count = 0

    async def embed_side_effect(**kwargs: object) -> MagicMock:
        nonlocal call_count
        batch = kwargs.get("texts", [])
        call_count += 1
        result = MagicMock()
        result.embeddings = [[0.1] * 1024 for _ in range(len(batch))]  # type: ignore[arg-type]
        return result

    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(side_effect=embed_side_effect)

    with (
        patch("app.services.llm.voyage.voyageai") as mock_voyage,
        patch("app.config.settings") as mock_settings,
    ):
        mock_voyage.AsyncClient.return_value = mock_client
        mock_settings.voyage_api_key = "test-key"
        mock_settings.voyage_model = "voyage-3"
        mock_settings.voyage_max_batch_size = 128

        from app.services.llm import voyage

        # Parchear el settings dentro del módulo directamente
        with patch.object(voyage, "settings") as mod_settings:
            mod_settings.voyage_api_key = "test-key"
            mod_settings.voyage_model = "voyage-3"
            mod_settings.voyage_max_batch_size = 128

            resultado = await voyage.embed_batch(textos)

    # 300 / 128 = ceil → 3 batches (128 + 128 + 44)
    assert mock_client.embed.await_count == 3
    assert len(resultado) == num_textos


@pytest.mark.asyncio
async def test_embed_batch_error_generico() -> None:
    """Cualquier error del SDK se wrappea como EmbeddingError."""
    textos = ["texto de prueba"]
    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(side_effect=Exception("connection refused"))

    with patch("app.services.llm.voyage.voyageai") as mock_voyage:
        mock_voyage.AsyncClient.return_value = mock_client

        from app.services.llm.voyage import embed_batch

        with (
            pytest.raises(EmbeddingError, match="connection refused"),
            patch("app.services.llm.voyage.wait_exponential", return_value=None),
        ):
            # tenacity reintentará 3 veces — aceleramos el test desactivando el wait
            await embed_batch(textos)


@pytest.mark.asyncio
async def test_embed_batch_rate_limit() -> None:
    """Error con 'rate limit' en el mensaje → EmbeddingRateLimitError."""
    textos = ["texto de prueba"]
    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(
        side_effect=Exception("rate limit exceeded, retry after 60s")
    )

    with patch("app.services.llm.voyage.voyageai") as mock_voyage:
        mock_voyage.AsyncClient.return_value = mock_client

        from app.services.llm.voyage import embed_batch

        with pytest.raises(EmbeddingRateLimitError):
            await embed_batch(textos)

    # EmbeddingRateLimitError NO debe reintentarse — se llama exactamente 1 vez
    mock_client.embed.assert_awaited_once()
