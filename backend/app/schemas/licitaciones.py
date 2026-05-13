"""Schemas Pydantic para los endpoints de licitaciones.

Expone solo campos públicos — excluye campos internos del pipeline:
raw_payload, search_vector, embedding, hash_contenido,
bases_descargadas_at, bases_procesadas_at, detalle_sincronizado_at.

Nota: uuid, datetime y los enums se importan en runtime porque Pydantic v2
los necesita para construir los schemas. Los noqa: TCH* son intencionales.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
import uuid  # noqa: TCH003

from pydantic import BaseModel, ConfigDict

from app.models.enums import FechaTipo, LicitacionEstado  # noqa: TCH001


class LicitacionListItem(BaseModel):
    """Item resumido para el listado de licitaciones."""

    model_config = ConfigDict(from_attributes=True)

    codigo: str
    nombre: str
    estado: LicitacionEstado
    tipo: str | None
    modalidad: str | None
    moneda: str
    monto_estimado: float | None
    fecha_publicacion: datetime | None
    fecha_cierre: datetime | None
    fecha_adjudicacion: datetime | None
    # Campo poblado manualmente desde el join con organismos
    organismo_nombre: str | None = None
    created_at: datetime
    updated_at: datetime


class LicitacionListResponse(BaseModel):
    """Respuesta paginada del listado de licitaciones."""

    model_config = ConfigDict(from_attributes=True)

    items: list[LicitacionListItem]
    total: int
    page: int
    page_size: int


class LicitacionFechaResponse(BaseModel):
    """Fecha del calendario de una licitación."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: FechaTipo
    fecha: datetime
    es_estimada: bool


class LicitacionItemResponse(BaseModel):
    """Item de línea de una licitación."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    numero_item: int
    unspsc_codigo: str | None
    unspsc_nombre: str | None
    nombre_producto: str | None
    descripcion: str | None
    cantidad: float | None
    unidad: str | None
    monto_unitario_estimado: float | None


class CriterioEvaluacionResponse(BaseModel):
    """Criterio de evaluación de una licitación."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    ponderacion: float
    tipo: str | None
    orden: int | None


class LicitacionDetalleResponse(BaseModel):
    """Detalle completo de una licitación con sus relaciones."""

    model_config = ConfigDict(from_attributes=True)

    # Campos del listado
    codigo: str
    nombre: str
    estado: LicitacionEstado
    tipo: str | None
    modalidad: str | None
    moneda: str
    monto_estimado: float | None
    fecha_publicacion: datetime | None
    fecha_cierre: datetime | None
    fecha_adjudicacion: datetime | None
    organismo_nombre: str | None = None
    created_at: datetime
    updated_at: datetime

    # Campos adicionales del detalle
    descripcion: str | None
    es_renovable: bool
    contacto_nombre: str | None
    contacto_email: str | None

    # Relaciones
    items: list[LicitacionItemResponse]
    fechas: list[LicitacionFechaResponse]
    criterios: list[CriterioEvaluacionResponse]
