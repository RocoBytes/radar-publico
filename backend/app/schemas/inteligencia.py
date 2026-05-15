"""Schemas Pydantic v2 para el endpoint de inteligencia de mercado.

Datos de contexto histórico del organismo comprador: volumen de licitaciones,
montos promedio y proveedores con mejor historial de adjudicación.
"""

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
    monto_promedio_organismo: float | None  # CLP
    top_proveedores: list[TopProveedor]
