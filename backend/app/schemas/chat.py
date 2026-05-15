"""Schemas Pydantic para el módulo de chat IA."""

from datetime import datetime
import uuid

from pydantic import BaseModel, Field

from app.models.enums import MensajeRol


class CitaSchema(BaseModel):
    """Referencia a un fragmento de bases técnicas citado en una respuesta."""

    chunk_id: str
    pagina: int | None
    fragmento: str  # preview ~200 chars


class MensajeCreate(BaseModel):
    """Body para enviar un nuevo mensaje en la conversación."""

    contenido: str = Field(..., min_length=1, max_length=2000)


class MensajeResponse(BaseModel):
    """Representación pública de un mensaje de conversación."""

    id: uuid.UUID
    rol: MensajeRol
    contenido: str
    citas: list[CitaSchema]
    modelo_usado: str | None
    tokens_input: int | None
    tokens_output: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversacionResponse(BaseModel):
    """Representación pública de una conversación con sus mensajes."""

    id: uuid.UUID
    licitacion_codigo: str | None
    mensajes: list[MensajeResponse]

    model_config = {"from_attributes": True}
