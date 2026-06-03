"""Modelos SQLAlchemy 2.0 — reflejo fiel de schema.sql.

Importar todos los modelos aquí para que Alembic los detecte
en alembic/env.py con: import app.models  # noqa: F401
"""

from app.models.adjudicacion import Adjudicacion
from app.models.analisis_ia import AnalisisBases, BorradorPropuesta
from app.models.api_log import ApiQuotaLog
from app.models.catalogos import Comuna, Region, Unspsc
from app.models.conversacion import ConversacionIA, ConversacionMensaje
from app.models.documento_base import DocumentoBase, DocumentoChunk
from app.models.empresa import Empresa
from app.models.enums import EmailFrecuencia, MensajeRol, PipelineEstado, PlanAnualStatus
from app.models.eventos_auditoria import AuditAction, EventoAuditoria
from app.models.interes import Interes, InteresTipo
from app.models.licitacion import (
    CriterioEvaluacion,
    Licitacion,
    LicitacionFecha,
    LicitacionItem,
)
from app.models.llm_usage_log import LlmUsageLog
from app.models.notificacion import Notificacion
from app.models.ordenes_compra import OrdenesCompra
from app.models.organismo import Organismo
from app.models.password_reset import PasswordResetToken
from app.models.pipeline import PipelineArchivo, PipelineChecklistItem, PipelineItem, PipelineNota
from app.models.plan_anual import PlanAnualLinea
from app.models.preferencias import PreferenciasNotificaciones
from app.models.proveedor import Proveedor
from app.models.radar import Radar
from app.models.refresh_token import RefreshToken
from app.models.ticket import TicketApi
from app.models.usuario import Usuario

__all__ = [
    "Adjudicacion",
    "AnalisisBases",
    "ApiQuotaLog",
    "BorradorPropuesta",
    "AuditAction",
    "Comuna",
    "ConversacionIA",
    "ConversacionMensaje",
    "CriterioEvaluacion",
    "DocumentoBase",
    "DocumentoChunk",
    "Empresa",
    "EventoAuditoria",
    "Interes",
    "InteresTipo",
    "Licitacion",
    "LlmUsageLog",
    "LicitacionFecha",
    "LicitacionItem",
    "EmailFrecuencia",
    "MensajeRol",
    "Notificacion",
    "OrdenesCompra",
    "PreferenciasNotificaciones",
    "Organismo",
    "PasswordResetToken",
    "PipelineArchivo",
    "PipelineEstado",
    "PipelineChecklistItem",
    "PipelineItem",
    "PipelineNota",
    "PlanAnualLinea",
    "PlanAnualStatus",
    "Proveedor",
    "Radar",
    "RefreshToken",
    "Region",
    "TicketApi",
    "Unspsc",
    "Usuario",
]
