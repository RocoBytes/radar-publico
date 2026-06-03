"""Tests unitarios para app.services.pdf.chunker."""

import pytest
import tiktoken

from app.services.pdf.chunker import Chunk, chunkear_documento
from app.services.pdf.exceptions import ChunkingError

_ENC = tiktoken.get_encoding("cl100k_base")


def _contar_tokens(texto: str) -> int:
    return len(_ENC.encode(texto))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_chunker_texto_corto() -> None:
    """Un texto que cabe en un solo chunk debe generar exactamente 1 chunk."""
    paginas = ["Este es un texto corto de prueba."]

    resultado = chunkear_documento(paginas)

    assert len(resultado) == 1
    assert resultado[0].orden == 0
    assert resultado[0].pagina_inicio == 0
    assert resultado[0].pagina_fin == 0
    assert "Este es un texto corto de prueba" in resultado[0].contenido
    assert resultado[0].tokens > 0


def test_chunker_multiples_paginas() -> None:
    """Tres páginas deben generar múltiples chunks con páginas correctas."""
    # Crear párrafos repetidos para asegurar que se genera más de un chunk
    parrafo = "Oración de prueba para llenar el chunk con suficiente contenido. " * 10
    paginas = [parrafo, parrafo, parrafo]

    resultado = chunkear_documento(paginas, max_tokens=100, overlap=10)

    assert len(resultado) > 1
    # Verificar que los ordenes son consecutivos
    ordenes = [c.orden for c in resultado]
    assert ordenes == list(range(len(resultado)))
    # Verificar que pagina_inicio <= pagina_fin en todos los chunks
    for chunk in resultado:
        assert chunk.pagina_inicio <= chunk.pagina_fin
    # El último chunk debe terminar en la última página
    assert resultado[-1].pagina_fin == 2


def test_chunker_overlap() -> None:
    """El segundo chunk debe iniciar con texto del final del primero (overlap)."""
    # Necesitamos texto suficiente para generar al menos 2 chunks
    parrafo_largo = "palabra " * 200  # ~200 tokens
    paginas = [parrafo_largo]

    resultado = chunkear_documento(paginas, max_tokens=100, overlap=20)

    assert len(resultado) >= 2

    # Extraer las últimas palabras del chunk 0
    palabras_fin_chunk0 = resultado[0].contenido.split()[-5:]
    # El chunk 1 debe contener alguna de esas palabras (overlap)
    palabras_inicio_chunk1 = resultado[1].contenido.split()[:10]
    overlap_encontrado = any(p in palabras_inicio_chunk1 for p in palabras_fin_chunk0)
    assert overlap_encontrado, (
        f"No se encontró overlap. Fin chunk0: {palabras_fin_chunk0}, "
        f"Inicio chunk1: {palabras_inicio_chunk1}"
    )


def test_chunker_paginas_vacias() -> None:
    """Lista vacía de páginas debe retornar lista vacía de chunks."""
    resultado = chunkear_documento([])

    assert resultado == []


def test_chunker_tokens_correctos() -> None:
    """Ningún chunk debe superar max_tokens."""
    parrafo = "contenido de prueba para verificar límite de tokens " * 20
    paginas = [parrafo, parrafo]
    max_tokens = 150

    resultado = chunkear_documento(paginas, max_tokens=max_tokens, overlap=20)

    assert len(resultado) > 0
    for chunk in resultado:
        tokens_reales = _contar_tokens(chunk.contenido)
        assert tokens_reales <= max_tokens, (
            f"Chunk {chunk.orden} tiene {tokens_reales} tokens, " f"máximo permitido {max_tokens}"
        )


def test_chunker_no_genera_chunks_vacios() -> None:
    """No debe generarse ningún chunk con contenido vacío."""
    paginas = ["   \n\n   \n", "Texto real aquí.", "   "]

    resultado = chunkear_documento(paginas)

    for chunk in resultado:
        assert chunk.contenido.strip() != "", f"Chunk {chunk.orden} está vacío"


def test_chunker_max_tokens_menor_que_overlap_lanza_error() -> None:
    """Debe lanzar ChunkingError si max_tokens <= overlap."""
    with pytest.raises(ChunkingError):
        chunkear_documento(["texto"], max_tokens=50, overlap=50)


def test_chunker_preserva_orden_de_paginas() -> None:
    """Los chunks deben referenciar páginas en orden ascendente."""
    paginas = [
        "Contenido de la página uno con bastante texto para generar chunks. " * 15,
        "Contenido de la página dos con bastante texto para generar chunks. " * 15,
        "Contenido de la página tres con bastante texto para generar chunks. " * 15,
    ]

    resultado = chunkear_documento(paginas, max_tokens=100, overlap=10)

    assert len(resultado) > 1
    paginas_inicio = [c.pagina_inicio for c in resultado]
    # Las páginas de inicio deben ser no-decrecientes
    assert paginas_inicio == sorted(
        paginas_inicio
    ), f"Las páginas de inicio no están en orden: {paginas_inicio}"


def test_chunker_tipo_retorno() -> None:
    """Debe retornar una lista de instancias Chunk con los campos correctos."""
    paginas = ["Texto de prueba para verificar tipos."]

    resultado = chunkear_documento(paginas)

    assert isinstance(resultado, list)
    assert all(isinstance(c, Chunk) for c in resultado)
    chunk = resultado[0]
    assert isinstance(chunk.orden, int)
    assert isinstance(chunk.contenido, str)
    assert isinstance(chunk.pagina_inicio, int)
    assert isinstance(chunk.pagina_fin, int)
    assert isinstance(chunk.tokens, int)
