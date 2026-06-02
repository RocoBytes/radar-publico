"""Endpoints REST para el chat IA sobre bases de licitaciones.

GET  /api/v1/chat/{licitacion_codigo}
     Obtiene o crea la conversación de la empresa para esa licitación.
     Retorna los últimos 30 mensajes.

POST /api/v1/chat/{licitacion_codigo}/mensaje
     Recibe el mensaje del usuario, busca chunks relevantes y emite
     la respuesta del asistente como Server-Sent Events (SSE).
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import TYPE_CHECKING
import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
import structlog

from app.api.deps import CurrentUser, DbDep, EmpresaDep  # noqa: TCH001
from app.models.conversacion import ConversacionIA, ConversacionMensaje
from app.models.enums import MensajeRol
from app.models.licitacion import Licitacion
from app.schemas.chat import ConversacionResponse, MensajeCreate, MensajeResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from app.models.documento_base import DocumentoChunk

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["chat"])

_HISTORIAL_MAXIMO = 30
_HISTORIAL_CONTEXTO = 10
_RATE_LIMIT_DIARIO = 100

_SYSTEM_PROMPT_CON_BASES = """\
Eres un asistente experto en bases de licitaciones del Mercado Público de Chile.

Licitación: {nombre}
Código: {codigo}

Fragmentos relevantes de las bases técnicas:
---
{contexto}
---

Instrucciones:
- Responde SOLO con la información de las bases proporcionadas.
- Si no encuentras la información, dilo claramente.
- Sé preciso con números, plazos y requisitos.
- Indica en qué página está la información cuando sea relevante.
- Responde en español.\
"""

_SYSTEM_PROMPT_SIN_BASES = """\
Eres un asistente de licitaciones del Mercado Público de Chile.
Las bases técnicas de esta licitación aún no han sido procesadas.
Informa al usuario que los documentos están siendo procesados \
y estarán disponibles pronto.\
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _construir_contexto(chunks: list[DocumentoChunk]) -> str:
    """Formatea los chunks recuperados para incluir en el system prompt."""
    partes: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        pag = f" (pág. {chunk.pagina_inicio})" if chunk.pagina_inicio else ""
        partes.append(f"[{i}]{pag}\n{chunk.contenido}")
    return "\n\n".join(partes)


def _construir_citas(chunks: list[DocumentoChunk]) -> list[dict[str, object]]:
    """Construye la lista de citas a partir de los chunks usados como contexto."""
    return [
        {
            "chunk_id": str(chunk.id),
            "pagina": chunk.pagina_inicio,
            "fragmento": chunk.contenido[:200],
        }
        for chunk in chunks
    ]


# ---------------------------------------------------------------------------
# SSE generator
# ---------------------------------------------------------------------------


async def _generar_respuesta(
    conversacion_id: uuid.UUID,
    empresa_id: uuid.UUID,
    mensaje_usuario: str,
    historial: list[ConversacionMensaje],
    licitacion_codigo: str,
    licitacion_nombre: str,
) -> AsyncGenerator[str, None]:
    """Generador SSE que hace streaming de la respuesta del asistente.

    Emite tres tipos de eventos:
    - delta:  fragmento de texto de la respuesta
    - citas:  lista de referencias a chunks al terminar
    - fin:    mensaje_id del mensaje assistant persistido
    - error:  si ocurre cualquier excepción
    """
    # Imports locales para evitar imports circulares con AsyncSessionLocal
    from app.db.session import AsyncSessionLocal
    from app.services.llm.client import chat_streaming
    from app.services.llm.usage_log import registrar_uso
    from app.services.search.vector import buscar_chunks_similares

    log = logger.bind(
        conversacion_id=str(conversacion_id),
        licitacion_codigo=licitacion_codigo,
    )

    try:
        # 1. Buscar chunks similares al query del usuario
        async with AsyncSessionLocal() as db_search:
            chunks = await buscar_chunks_similares(
                db_search, licitacion_codigo, mensaje_usuario
            )

        # 2. Construir system prompt según disponibilidad de bases
        if chunks:
            contexto = _construir_contexto(chunks)
            system_prompt = _SYSTEM_PROMPT_CON_BASES.format(
                nombre=licitacion_nombre,
                codigo=licitacion_codigo,
                contexto=contexto,
            )
        else:
            system_prompt = _SYSTEM_PROMPT_SIN_BASES

        # 3. Construir lista de mensajes para LiteLLM
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for msg in historial[-_HISTORIAL_CONTEXTO:]:
            if msg.rol in (MensajeRol.user, MensajeRol.assistant):
                messages.append({"role": msg.rol.value, "content": msg.contenido})
        messages.append({"role": "user", "content": mensaje_usuario})

        # 4. Streaming — acumular texto completo para persistir al final
        texto_completo = ""
        async for delta in chat_streaming(messages):
            texto_completo += delta
            yield f"data: {json.dumps({'tipo': 'delta', 'texto': delta})}\n\n"

        # 5. Persistir el mensaje del asistente en sesión fresca
        citas = _construir_citas(chunks)
        nuevo_mensaje_id = uuid.uuid4()

        async with AsyncSessionLocal() as db_write:
            mensaje_assistant = ConversacionMensaje(
                id=nuevo_mensaje_id,
                conversacion_id=conversacion_id,
                rol=MensajeRol.assistant,
                contenido=texto_completo,
                citas=citas,
                modelo_usado=None,  # LiteLLM no expone el modelo final en streaming
                tokens_input=None,
                tokens_output=None,
                costo_estimado=None,
            )
            db_write.add(mensaje_assistant)

            # Registrar uso de IA (tokens desconocidos en streaming sin usage block)
            await registrar_uso(
                db_write,
                provider="anthropic",
                modelo="claude-opus-4-7",
                tokens_in=0,
                tokens_out=0,
                feature="chat_bases_licitacion",
                empresa_id=empresa_id,
            )

            await db_write.commit()

        log.info("chat_respuesta_generada", mensaje_id=str(nuevo_mensaje_id))

        # 6. Emitir citas y señal de fin
        yield f"data: {json.dumps({'tipo': 'citas', 'citas': citas})}\n\n"
        fin_event = json.dumps({"tipo": "fin", "mensaje_id": str(nuevo_mensaje_id)})
        yield f"data: {fin_event}\n\n"

    except Exception as exc:
        log.error("chat_streaming_error", error=str(exc))
        yield f"data: {json.dumps({'tipo': 'error', 'detail': 'Error interno al procesar la consulta'})}\n\n"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{licitacion_codigo}",
    response_model=ConversacionResponse,
    summary="Obtiene o crea conversación IA para una licitación",
)
async def obtener_conversacion(
    licitacion_codigo: str,
    db: DbDep,
    _current_user: CurrentUser,
    empresa: EmpresaDep,
) -> ConversacionResponse:
    """Retorna la conversación de la empresa para la licitación indicada.

    Si no existe, la crea. Incluye los últimos 30 mensajes ordenados por
    created_at ascendente.
    """
    # Verificar que la licitación existe
    licitacion = (
        await db.execute(
            select(Licitacion).where(Licitacion.codigo == licitacion_codigo)
        )
    ).scalar_one_or_none()

    if licitacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Licitación '{licitacion_codigo}' no encontrada",
        )

    # Buscar conversación existente
    conversacion = (
        await db.execute(
            select(ConversacionIA)
            .where(
                ConversacionIA.empresa_id == empresa.id,
                ConversacionIA.licitacion_codigo == licitacion_codigo,
            )
            .options(selectinload(ConversacionIA.mensajes))
        )
    ).scalar_one_or_none()

    if conversacion is None:
        conversacion = ConversacionIA(
            empresa_id=empresa.id,
            licitacion_codigo=licitacion_codigo,
            titulo=licitacion.nombre[:255] if licitacion.nombre else None,
        )
        db.add(conversacion)
        await db.flush()
        # Relación vacía para serialización
        conversacion.mensajes = []

    # Retornar los últimos 30 mensajes ordenados cronológicamente
    mensajes_ordenados = sorted(
        conversacion.mensajes,
        key=lambda m: m.created_at,
    )[-_HISTORIAL_MAXIMO:]

    return ConversacionResponse(
        id=conversacion.id,
        licitacion_codigo=conversacion.licitacion_codigo,
        mensajes=[MensajeResponse.model_validate(m) for m in mensajes_ordenados],
    )


@router.post(
    "/{licitacion_codigo}/mensaje",
    summary="Envía un mensaje y recibe respuesta en streaming (SSE)",
)
async def enviar_mensaje(
    licitacion_codigo: str,
    data: MensajeCreate,
    db: DbDep,
    _current_user: CurrentUser,
    empresa: EmpresaDep,
) -> StreamingResponse:
    """Procesa el mensaje del usuario y retorna la respuesta del asistente vía SSE.

    Eventos emitidos:
    - ``delta``: fragmento de texto
    - ``citas``: referencias a fragmentos de bases técnicas
    - ``fin``:   mensaje_id del mensaje assistant persistido
    - ``error``: si ocurre algún fallo

    Límite: 100 mensajes de usuario por empresa por día (UTC).
    """
    # 1. Verificar que la licitación existe
    licitacion = (
        await db.execute(
            select(Licitacion).where(Licitacion.codigo == licitacion_codigo)
        )
    ).scalar_one_or_none()

    if licitacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Licitación '{licitacion_codigo}' no encontrada",
        )

    # 2. Rate limit: contar mensajes user del día actual (UTC) para esta empresa
    today_start = datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    mensajes_hoy: int = (
        await db.execute(
            select(func.count(ConversacionMensaje.id))
            .join(
                ConversacionIA,
                ConversacionMensaje.conversacion_id == ConversacionIA.id,
            )
            .where(
                ConversacionIA.empresa_id == empresa.id,
                ConversacionMensaje.rol == MensajeRol.user,
                ConversacionMensaje.created_at >= today_start,
            )
        )
    ).scalar_one()

    if mensajes_hoy >= _RATE_LIMIT_DIARIO:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Límite diario de {_RATE_LIMIT_DIARIO} mensajes alcanzado. "
                "Intentá de nuevo mañana."
            ),
        )

    # 3. Obtener o crear la conversación
    conversacion = (
        await db.execute(
            select(ConversacionIA)
            .where(
                ConversacionIA.empresa_id == empresa.id,
                ConversacionIA.licitacion_codigo == licitacion_codigo,
            )
            .options(selectinload(ConversacionIA.mensajes))
        )
    ).scalar_one_or_none()

    if conversacion is None:
        conversacion = ConversacionIA(
            empresa_id=empresa.id,
            licitacion_codigo=licitacion_codigo,
            titulo=licitacion.nombre[:255] if licitacion.nombre else None,
        )
        db.add(conversacion)
        await db.flush()
        conversacion.mensajes = []

    # 4. Persistir el mensaje del usuario
    mensaje_usuario_obj = ConversacionMensaje(
        conversacion_id=conversacion.id,
        rol=MensajeRol.user,
        contenido=data.contenido,
        citas=[],
    )
    db.add(mensaje_usuario_obj)
    await db.commit()

    # 5. Capturar historial antes de cerrar la sesión de request
    historial = sorted(conversacion.mensajes, key=lambda m: m.created_at)

    licitacion_nombre = licitacion.nombre or licitacion_codigo

    return StreamingResponse(
        content=_generar_respuesta(
            conversacion_id=conversacion.id,
            empresa_id=empresa.id,
            mensaje_usuario=data.contenido,
            historial=historial,
            licitacion_codigo=licitacion_codigo,
            licitacion_nombre=licitacion_nombre,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
