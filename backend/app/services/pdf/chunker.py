"""Módulo de chunking de texto para RAG en Radar Público."""

from dataclasses import dataclass

import tiktoken

from app.services.pdf.exceptions import ChunkingError

_ENCODING_NAME = "cl100k_base"


@dataclass(frozen=True)
class Chunk:
    """Fragmento de texto listo para indexar y embeddear."""

    orden: int
    contenido: str
    pagina_inicio: int
    pagina_fin: int
    tokens: int


def _contar_tokens(texto: str, enc: tiktoken.Encoding) -> int:
    """Cuenta los tokens de un texto usando el encoding dado."""
    return len(enc.encode(texto))


def _dividir_en_parrafos(texto: str) -> list[str]:
    """Divide un texto en párrafos, subdividiendo los muy largos por salto de línea."""
    parrafos: list[str] = []
    for bloque in texto.split("\n\n"):
        bloque = bloque.strip()
        if not bloque:
            continue
        # Subdividir por \n si el bloque es un único párrafo largo
        sublineas = [s.strip() for s in bloque.split("\n") if s.strip()]
        if len(sublineas) > 1:
            parrafos.extend(sublineas)
        else:
            parrafos.append(bloque)
    return parrafos


def chunkear_documento(
    paginas: list[str],
    max_tokens: int = 800,
    overlap: int = 100,
) -> list[Chunk]:
    """Divide el texto de un documento en chunks solapados para RAG.

    Cada chunk respeta el límite de tokens indicado. Se aplica un overlap
    de `overlap` tokens entre chunks consecutivos para mantener contexto.
    El proceso es síncrono — debe invocarse desde asyncio.to_thread en tareas Celery.

    Args:
        paginas: Lista de strings, uno por página del documento.
        max_tokens: Máximo de tokens por chunk (por defecto 800).
        overlap: Tokens de solapamiento entre chunks consecutivos (por defecto 100).

    Returns:
        Lista de Chunk ordenada por posición en el documento.

    Raises:
        ChunkingError: Si max_tokens es demasiado pequeño para ser útil.
    """
    if not paginas:
        return []

    if max_tokens <= overlap:
        raise ChunkingError(
            f"max_tokens ({max_tokens}) debe ser mayor que overlap ({overlap})"
        )

    enc = tiktoken.get_encoding(_ENCODING_NAME)

    # Colectar (párrafo, índice_de_página) para rastrear la página de origen
    parrafos_con_pagina: list[tuple[str, int]] = []
    for idx_pagina, texto_pagina in enumerate(paginas):
        for parrafo in _dividir_en_parrafos(texto_pagina):
            parrafos_con_pagina.append((parrafo, idx_pagina))

    if not parrafos_con_pagina:
        return []

    chunks: list[Chunk] = []
    buffer_textos: list[str] = []
    buffer_paginas: list[int] = []
    buffer_tokens: int = 0
    orden = 0

    def _guardar_chunk() -> None:
        nonlocal orden
        contenido = " ".join(buffer_textos).strip()
        if not contenido:
            return
        chunks.append(
            Chunk(
                orden=orden,
                contenido=contenido,
                pagina_inicio=buffer_paginas[0],
                pagina_fin=buffer_paginas[-1],
                tokens=buffer_tokens,
            )
        )
        orden += 1

    def _calcular_overlap_textos() -> tuple[list[str], list[int], int]:
        """Devuelve (textos, páginas, tokens) del overlap del buffer actual."""
        overlap_textos: list[str] = []
        overlap_paginas: list[int] = []
        overlap_tok = 0
        # Recorrer el buffer desde el final hasta alcanzar `overlap` tokens
        for texto, pagina in zip(
            reversed(buffer_textos), reversed(buffer_paginas), strict=False
        ):
            tok = _contar_tokens(texto, enc)
            if overlap_tok + tok > overlap:
                break
            overlap_textos.insert(0, texto)
            overlap_paginas.insert(0, pagina)
            overlap_tok += tok
        return overlap_textos, overlap_paginas, overlap_tok

    for parrafo, idx_pagina in parrafos_con_pagina:
        tok_parrafo = _contar_tokens(parrafo, enc)

        # Párrafo largo → dividir en ventanas solapadas y guardar directamente
        if tok_parrafo > max_tokens:
            if buffer_textos:
                _guardar_chunk()
                buffer_textos, buffer_paginas, buffer_tokens = [], [], 0

            tokens_enc = enc.encode(parrafo)
            step = max_tokens - overlap
            for pos in range(0, len(tokens_enc), step):
                frag_tokens = tokens_enc[pos : pos + max_tokens]
                if not frag_tokens:
                    break
                fragmento = enc.decode(frag_tokens)
                chunks.append(
                    Chunk(
                        orden=orden,
                        contenido=fragmento,
                        pagina_inicio=idx_pagina,
                        pagina_fin=idx_pagina,
                        tokens=len(frag_tokens),
                    )
                )
                orden += 1
            continue

        # Si agregar este párrafo supera el límite → guardar y comenzar nuevo chunk
        if buffer_tokens + tok_parrafo > max_tokens and buffer_textos:
            _guardar_chunk()
            ov_textos, ov_paginas, ov_tok = _calcular_overlap_textos()
            buffer_textos = ov_textos
            buffer_paginas = ov_paginas
            buffer_tokens = ov_tok

        buffer_textos.append(parrafo)
        buffer_paginas.append(idx_pagina)
        buffer_tokens += tok_parrafo

    # Guardar el último chunk si quedó texto
    if buffer_textos:
        _guardar_chunk()

    return chunks
