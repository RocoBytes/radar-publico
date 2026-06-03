"""Schemas Pydantic v2 para el endpoint de inteligencia de mercado.

Datos de contexto histórico del organismo comprador: volumen de licitaciones,
montos promedio y proveedores con mejor historial de adjudicación.
Incluye el análisis de admisibilidad derivado del análisis de bases IA.
"""

from typing import Literal

from pydantic import BaseModel


class TopProveedor(BaseModel):
    """Proveedor con mayor número de adjudicaciones en el organismo."""

    rut: str
    razon_social: str
    licitaciones_ganadas: int
    monto_total: float | None  # CLP, None si todas las adjudicaciones tienen monto None


class InteligenciaResponse(BaseModel):
    """Respuesta de inteligencia de mercado para una licitación.

    Agrega estadísticas históricas del organismo comprador en los últimos
    2 años para ayudar al proveedor a dimensionar su oferta.
    """

    organismo_nombre: str | None
    total_licitaciones_organismo: int
    monto_promedio_organismo: float | None  # CLP (estimado, de la licitacion)
    top_proveedores: list[TopProveedor]

    # Módulo 3: datos de adjudicaciones reales
    proveedores_unicos_organismo: int  # diversidad de proveedores en el organismo
    precio_min_organismo: float | None  # CLP mínimo adjudicado real en el organismo
    precio_max_organismo: float | None  # CLP máximo adjudicado real en el organismo
    top_competidores_rubro: list[TopProveedor]  # ganadores en el mismo UNSPSC


# ── Admisibilidad ─────────────────────────────────────────────────────────────

TipoItemAdmisibilidad = Literal["restriccion", "documento", "requisito"]
UrgenciaAdmisibilidad = Literal["alta", "media", "baja"]
NivelRiesgo = Literal["bajo", "medio", "alto"]


class ItemAdmisibilidad(BaseModel):
    """Un requisito formal que puede causar inadmisibilidad si no se cumple."""

    tipo: TipoItemAdmisibilidad
    descripcion: str
    urgencia: UrgenciaAdmisibilidad


class InadmisibilidadResponse(BaseModel):
    """Evaluación de riesgo de inadmisibilidad basada en el análisis de bases IA.

    Derivada de analisis_bases: restricciones + documentos_obligatorios +
    requisitos_tecnicos obligatorios. No requiere llamada LLM adicional.

    analisis_disponible=False cuando no existe AnalisisBases en status=listo.
    En ese caso todos los demás campos son None o lista vacía.
    """

    analisis_disponible: bool
    nivel_riesgo: NivelRiesgo | None
    items: list[ItemAdmisibilidad]
    resumen: str | None
