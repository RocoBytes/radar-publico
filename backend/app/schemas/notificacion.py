"""Schemas Pydantic para los endpoints de notificaciones."""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
import uuid  # noqa: TCH003

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotifCanal, NotifStatus, NotifTipo  # noqa: TCH001


class NotificacionResponse(BaseModel):
    """Representación pública de una notificación."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: NotifTipo
    canal: NotifCanal
    status: NotifStatus
    titulo: str
    cuerpo: str
    licitacion_codigo: str | None
    radar_id: uuid.UUID | None
    leida_at: datetime | None
    created_at: datetime


class NotificacionesResumenResponse(BaseModel):
    """Resumen de notificaciones in_app para el widget de campana."""

    unread_count: int
    items: list[NotificacionResponse]  # últimas 10 in_app
