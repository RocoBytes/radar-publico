"""Schemas Pydantic para los endpoints de intereses.

No se expone el campo `embedding` — es interno del pipeline de vectorización.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
import uuid  # noqa: TCH003

from pydantic import BaseModel, ConfigDict, Field

from app.models.interes import InteresTipo  # noqa: TCH001


class InteresResponse(BaseModel):
    """Representación pública de un interés comercial."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: InteresTipo
    valor: str
    prioridad: int
    created_at: datetime


class InteresCreateRequest(BaseModel):
    """Datos requeridos para crear un interés."""

    tipo: InteresTipo
    valor: str = Field(min_length=1, max_length=255)
    prioridad: int = Field(default=5, ge=1, le=10)


class InteresListResponse(BaseModel):
    """Respuesta del listado de intereses."""

    model_config = ConfigDict(from_attributes=True)

    items: list[InteresResponse]
    total: int
