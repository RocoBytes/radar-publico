"""Modelo SQLAlchemy para la tabla eventos_auditoria.

Tabla append-only. No se hacen UPDATEs ni DELETEs. Solo INSERT.
Las constantes de AuditAction son strings libres — no un enum SQL.
"""

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditAction:
    LOGIN_OK = "auth.login.success"
    LOGIN_FAILED = "auth.login.failed"
    LOGOUT = "auth.logout"
    TOKEN_REFRESHED = "auth.token.refreshed"
    PASSWORD_CHANGED = "auth.password.changed"
    PASSWORD_RESET_REQUESTED = "auth.password.reset.requested"
    PASSWORD_RESET_COMPLETED = "auth.password.reset.completed"
    USER_CREATED = "user.created"


class EventoAuditoria(Base):
    """Registro inmutable de acciones sensibles del sistema."""

    __tablename__ = "eventos_auditoria"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("empresas.id", ondelete="SET NULL"),
        nullable=True,
    )
    accion: Mapped[str] = mapped_column(String(100), nullable=False)
    recurso_tipo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recurso_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "metadata" es reservado en SQLAlchemy — se mapea con name=
    info: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    def __repr__(self) -> str:
        return f"<EventoAuditoria id={self.id} accion={self.accion!r}>"
