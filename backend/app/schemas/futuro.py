"""Schemas Pydantic para el módulo de Futuro (renovaciones y plan anual).

Cubre el Epic 9 de la spec: feed de licitaciones adjudicadas renovables
con fecha estimada de término de contrato, y el plan anual de compras
de los organismos.
"""

from datetime import datetime
import uuid

from pydantic import BaseModel


class RenovacionResponse(BaseModel):
    """Licitación adjudicada con potencial de renovación."""

    model_config = {"from_attributes": True}

    licitacion_codigo: str
    nombre: str
    organismo_nombre: str | None
    monto_estimado: float | None
    fecha_adjudicacion: datetime | None
    duracion_estimada_meses: int | None
    fecha_estimada_termino_contrato: datetime | None
    dias_para_termino: int | None


class RenovacionesListResponse(BaseModel):
    """Respuesta paginada del feed de renovaciones."""

    total: int
    page: int
    page_size: int
    items: list[RenovacionResponse]


class PlanAnualLineaResponse(BaseModel):
    """Línea del plan anual de compras de un organismo."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    ano: int
    codigo_organismo: int
    descripcion: str
    unspsc_codigo: str | None
    unspsc_nombre: str | None
    monto_estimado: float | None
    moneda: str
    mes_estimado: int | None
    modalidad: str | None
    status: str
    licitacion_codigo: str | None
    created_at: datetime


class PlanAnualListResponse(BaseModel):
    """Respuesta paginada del plan anual."""

    total: int
    page: int
    page_size: int
    items: list[PlanAnualLineaResponse]
