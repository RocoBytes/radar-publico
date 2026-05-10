"""Modelos SQLAlchemy 2.0 — reflejo fiel de schema.sql.

Importar todos los modelos aquí para que Alembic los detecte
en alembic/env.py con: import app.models  # noqa: F401
"""

from app.models.api_log import ApiQuotaLog
from app.models.empresa import Empresa
from app.models.eventos_auditoria import AuditAction, EventoAuditoria
from app.models.licitacion import (
    CriterioEvaluacion,
    Licitacion,
    LicitacionFecha,
    LicitacionItem,
)
from app.models.organismo import Organismo
from app.models.password_reset import PasswordResetToken
from app.models.proveedor import Proveedor
from app.models.refresh_token import RefreshToken
from app.models.ticket import TicketApi
from app.models.usuario import Usuario

__all__ = [
    "ApiQuotaLog",
    "AuditAction",
    "CriterioEvaluacion",
    "Empresa",
    "EventoAuditoria",
    "Licitacion",
    "LicitacionFecha",
    "LicitacionItem",
    "Organismo",
    "PasswordResetToken",
    "Proveedor",
    "RefreshToken",
    "TicketApi",
    "Usuario",
]
