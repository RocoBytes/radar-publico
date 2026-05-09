"""Modelo SQLAlchemy para la tabla api_quota_log.

Una fila por cada request a la API de Mercado Público.
Permite monitorear consumo de cuota y detectar saturación.
Regla de oro: sin PII en logs — ticket_id (FK), nunca el ticket en claro.
"""

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApiQuotaLog(Base):
    """Log de cada request a la API de Mercado Público."""

    __tablename__ = "api_quota_log"

    # bigserial — tabla append-only que crece rápido
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Referencias (nullable: si empresa/ticket se elimina, el log se conserva)
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets_api.id", ondelete="SET NULL"),
        nullable=True,
    )
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("empresas.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Datos del request
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    metodo: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    duracion_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Sin PII — solo mensaje técnico de error si aplica
    error_mensaje: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        Index("idx_quota_ticket_fecha", "ticket_id", text("created_at DESC")),
        Index("idx_quota_empresa_fecha", "empresa_id", text("created_at DESC")),
    )

    def __repr__(self) -> str:
        return (
            f"<ApiQuotaLog id={self.id} endpoint={self.endpoint!r} "
            f"status={self.status_code}>"
        )
