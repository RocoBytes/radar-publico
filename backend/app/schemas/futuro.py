"""Schemas Pydantic para el módulo de Futuro (renovaciones).

Cubre el Epic 9 de la spec: feed de licitaciones adjudicadas renovables
con fecha estimada de término de contrato.
"""

from datetime import datetime

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
