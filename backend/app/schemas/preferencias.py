"""Schemas Pydantic para los endpoints de preferencias de notificaciones."""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PreferenciasResponse(BaseModel):
    """Respuesta con las preferencias de notificación de la empresa."""

    model_config = ConfigDict(from_attributes=True)

    email_activo: bool
    email_frecuencia: str  # "instantaneo" | "diario" | "semanal"
    email_score_minimo: int | None
    whatsapp_activo: bool
    whatsapp_solo_criticas: bool
    whatsapp_score_minimo: int | None
    whatsapp_pausado_hasta: datetime | None
    in_app_activo: bool
    tipos_activos: list[str]
    updated_at: datetime


class PreferenciasUpdateRequest(BaseModel):
    """Request para actualización parcial (PATCH) de preferencias.

    Todos los campos son opcionales.
    """

    email_activo: bool | None = None
    email_frecuencia: Literal["instantaneo", "diario", "semanal"] | None = None
    email_score_minimo: int | None = Field(default=None, ge=0, le=100)
    whatsapp_activo: bool | None = None
    whatsapp_solo_criticas: bool | None = None
    whatsapp_score_minimo: int | None = Field(default=None, ge=0, le=100)
    in_app_activo: bool | None = None
    tipos_activos: list[str] | None = None
