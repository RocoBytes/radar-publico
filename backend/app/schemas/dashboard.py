"""Schemas Pydantic para los endpoints del dashboard."""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
import uuid  # noqa: TCH003

from pydantic import BaseModel

from app.models.enums import LicitacionEstado, PipelineEstado  # noqa: TCH001


class LicitacionEnTopResponse(BaseModel):
    """Datos mínimos de la licitación para el top-5 del dashboard."""

    codigo: str
    nombre: str
    estado: LicitacionEstado
    fecha_cierre: datetime | None
    monto_estimado: float | None
    organismo_nombre: str | None


class TopOportunidad(BaseModel):
    """Ítem resumido para el top-5 de oportunidades del dashboard."""

    id: uuid.UUID
    score: int | None
    estado: PipelineEstado
    licitacion: LicitacionEnTopResponse


class DashboardResumenResponse(BaseModel):
    """Respuesta del endpoint GET /dashboard/resumen."""

    oportunidades_activas: int
    nuevas_hoy: int
    proximas_a_cerrar: int
    en_pipeline: int
    top_oportunidades: list[TopOportunidad]
    ultima_sincronizacion: datetime | None


class SegmentoItem(BaseModel):
    """Un segmento UNSPSC con cantidad de licitaciones activas."""

    codigo: str
    nombre: str
    cantidad: int


class DashboardSegmentosResponse(BaseModel):
    """Respuesta del endpoint GET /dashboard/segmentos."""

    segmentos: list[SegmentoItem]
