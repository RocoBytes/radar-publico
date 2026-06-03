"""Schemas Pydantic v2 para los endpoints de dashboard del panel admin.

Expone KPIs operacionales y desglose de costos de IA por empresa.
Sin PII — solo IDs internos y razon_social (dato empresarial, no personal).
"""

import uuid

from pydantic import BaseModel


class AdminKpisResponse(BaseModel):
    """KPIs operacionales del panel de administración."""

    empresas_activas: int
    licitaciones_indexadas: int
    mensajes_ia_hoy: int
    costo_ia_mes: float  # USD, siempre >= 0.0


class CostoIaEmpresa(BaseModel):
    """Desglose de uso y costo de IA para una empresa en el período."""

    empresa_id: uuid.UUID
    razon_social: str
    mensajes_mes: int
    tokens_input_mes: int
    tokens_output_mes: int
    costo_mes: float  # USD, siempre >= 0.0


class AdminCostosIaResponse(BaseModel):
    """Respuesta con el desglose de costos de IA por empresa."""

    meses: int
    empresas: list[CostoIaEmpresa]
