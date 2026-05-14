"""Schemas Pydantic para los endpoints del pipeline de licitaciones.

Nota: organismo_nombre no viene de from_attributes porque está en una relación
anidada (licitacion.organismo.nombre) — se construye manualmente en el endpoint.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from decimal import Decimal  # noqa: TCH003
from typing import Any
import uuid  # noqa: TCH003

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LicitacionEstado, PipelineEstado  # noqa: TCH001


class LicitacionEnPipelineResponse(BaseModel):
    """Datos básicos de la licitación incluidos en cada item del pipeline."""

    codigo: str
    nombre: str
    estado: LicitacionEstado
    tipo: str | None
    moneda: str
    monto_estimado: float | None
    fecha_publicacion: datetime | None
    fecha_cierre: datetime | None
    organismo_nombre: str | None


class PipelineNotaResponse(BaseModel):
    """Nota textual de un ítem del pipeline."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contenido: str
    created_at: datetime


class PipelineItemListItem(BaseModel):
    """Ítem resumido para el listado del pipeline (sin notas)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    estado: PipelineEstado
    score: int | None
    score_justificacion: dict[str, Any] | None
    razon_descarte: str | None
    monto_postulado: float | None
    resultado_observaciones: str | None
    detected_by_radar_id: uuid.UUID | None
    notas_count: int
    created_at: datetime
    updated_at: datetime
    licitacion: LicitacionEnPipelineResponse


class PipelineItemResponse(PipelineItemListItem):
    """Ítem completo con notas para la vista de detalle."""

    notas: list[PipelineNotaResponse]


class PipelineListResponse(BaseModel):
    """Respuesta paginada del listado del pipeline."""

    items: list[PipelineItemListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class PipelineItemUpdateRequest(BaseModel):
    """Campos actualizables de un ítem del pipeline (PATCH semántico)."""

    estado: PipelineEstado | None = None
    razon_descarte: str | None = Field(default=None, max_length=2000)
    monto_postulado: Decimal | None = Field(default=None, ge=0)
    resultado_observaciones: str | None = Field(default=None, max_length=5000)


class PipelineNotaCreateRequest(BaseModel):
    """Datos para crear una nota en un ítem del pipeline."""

    contenido: str = Field(min_length=1, max_length=5000)
