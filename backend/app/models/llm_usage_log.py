"""Modelo SQLAlchemy para la tabla llm_usage_log.

Regla #23: toda llamada a LLM debe loggear provider, modelo, tokens y costo.
Permite controlar costos por empresa y detectar abuso.
Sin PII en ninguna columna.
"""

from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class LlmUsageLog(Base):
    """Registro de cada llamada al LLM. Append-only, nunca se actualiza."""

    __tablename__ = "llm_usage_log"

    # bigserial — tabla de alto volumen
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Nullable: si la empresa se elimina, el log se conserva para auditoría de costos.
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("empresas.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Identificación de la feature que generó el gasto
    feature: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    modelo: Mapped[str] = mapped_column(String(100), nullable=False)

    # Uso de tokens
    tokens_input: Mapped[int] = mapped_column(nullable=False, server_default="0")
    tokens_output: Mapped[int] = mapped_column(nullable=False, server_default="0")

    # Costo estimado en USD (puede ser None si no se puede calcular)
    costo_estimado: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
    )

    # Estado de la llamada: 'ok', 'error', 'timeout', etc.
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_llm_usage_empresa_fecha", "empresa_id", "created_at"),
        Index("idx_llm_usage_feature_fecha", "feature", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<LlmUsageLog id={self.id} feature={self.feature!r} "
            f"modelo={self.modelo!r} status={self.status!r}>"
        )
