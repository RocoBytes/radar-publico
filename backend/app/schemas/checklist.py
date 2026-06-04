"""Schemas Pydantic para el checklist documental por pipeline_item.

Usado por los endpoints GET/POST/PATCH/DELETE /pipeline/{id}/checklist
y por el endpoint de bootstrap POST /pipeline/{id}/checklist/bootstrap-from-analysis.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
import uuid  # noqa: TCH003

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ChecklistItemEstado, ChecklistItemOrigen  # noqa: TCH001


class ChecklistItemBase(BaseModel):
    """Campos comunes para creación y actualización de un ítem del checklist."""

    nombre: str = Field(min_length=1, max_length=255)
    descripcion: str | None = Field(default=None, max_length=2000)
    obligatorio: bool = False
    orden: int = Field(default=0, ge=0, le=999)


class ChecklistItemCreate(ChecklistItemBase):
    """Payload para crear un ítem manualmente.

    El origen siempre queda forzado a 'manual' en el servicio.
    """

    pass


class ChecklistItemUpdate(BaseModel):
    """Payload PATCH — todos los campos son opcionales (semántica partial update).

    Si estado cambia a 'completado', el servicio setea completed_at = now().
    Si estado sale de 'completado', el servicio limpia completed_at.
    """

    nombre: str | None = Field(default=None, min_length=1, max_length=255)
    descripcion: str | None = Field(default=None, max_length=2000)
    obligatorio: bool | None = None
    estado: ChecklistItemEstado | None = None
    orden: int | None = Field(default=None, ge=0, le=999)


class ChecklistItemResponse(BaseModel):
    """Representación completa de un ítem del checklist (lectura)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pipeline_item_id: uuid.UUID
    nombre: str
    descripcion: str | None
    obligatorio: bool
    estado: ChecklistItemEstado
    origen: ChecklistItemOrigen
    orden: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ChecklistBootstrapResponse(BaseModel):
    """Resultado del endpoint de bootstrap desde análisis IA.

    creados: ítems nuevos insertados en esta llamada.
    omitidos: ítems que ya existían y fueron ignorados (idempotencia).
    items: lista completa actual del checklist después del bootstrap.
    """

    creados: int
    omitidos: int
    items: list[ChecklistItemResponse]
