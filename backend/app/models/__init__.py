"""Modelos SQLAlchemy 2.0 — reflejo fiel de schema.sql.

Importar todos los modelos aquí para que Alembic los detecte
en alembic/env.py con: import app.models  # noqa: F401
"""

from app.models.api_log import ApiQuotaLog
from app.models.empresa import Empresa
from app.models.licitacion import (
    CriterioEvaluacion,
    Licitacion,
    LicitacionFecha,
    LicitacionItem,
)
from app.models.organismo import Organismo
from app.models.proveedor import Proveedor
from app.models.ticket import TicketApi
from app.models.usuario import Usuario

__all__ = [
    "ApiQuotaLog",
    "CriterioEvaluacion",
    "Empresa",
    "Licitacion",
    "LicitacionFecha",
    "LicitacionItem",
    "Organismo",
    "Proveedor",
    "TicketApi",
    "Usuario",
]
