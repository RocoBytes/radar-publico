"""Schemas Pydantic para los endpoints de radares.

FiltrosRadar define los criterios de búsqueda que se persisten en JSONB.
Se valida en entrada (create/update) y se retorna tal cual en las respuestas.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from typing import Any
import uuid  # noqa: TCH003

from pydantic import BaseModel, ConfigDict, Field


class FiltrosRadar(BaseModel):
    """Criterios de búsqueda de un radar. Todos los campos son opcionales."""

    model_config = ConfigDict(extra="ignore")

    q: str | None = Field(default=None, max_length=500)
    estado: str | None = Field(default=None, max_length=20)
    unspsc_codigo: str | None = Field(default=None, min_length=2, max_length=8)
    tipo: str | None = Field(default=None, max_length=10)
    monto_min: float | None = Field(default=None, ge=0)
    monto_max: float | None = Field(default=None, ge=0)


class RadarCreateRequest(BaseModel):
    """Datos para crear un nuevo radar."""

    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=1000)
    filtros: FiltrosRadar
    notif_canal: str = Field(default="email", max_length=20)
    notif_frecuencia: str = Field(default="instantaneo", max_length=20)
    notif_score_minimo: int | None = Field(default=70, ge=0, le=100)


class RadarUpdateRequest(BaseModel):
    """Campos actualizables de un radar (todos opcionales — PATCH semántico)."""

    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    descripcion: str | None = None
    filtros: FiltrosRadar | None = None
    activo: bool | None = None
    notif_canal: str | None = Field(default=None, max_length=20)
    notif_frecuencia: str | None = Field(default=None, max_length=20)
    notif_score_minimo: int | None = Field(default=None, ge=0, le=100)


class RadarResponse(BaseModel):
    """Representación pública de un radar."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    descripcion: str | None
    filtros: dict[str, Any]
    activo: bool
    notif_canal: str
    notif_frecuencia: str
    notif_score_minimo: int | None
    ultima_ejecucion_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RadarListResponse(BaseModel):
    """Respuesta del listado de radares."""

    items: list[RadarResponse]
    total: int
