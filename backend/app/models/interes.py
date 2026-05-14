"""Modelo SQLAlchemy para la tabla intereses.

Intereses de una empresa: rubros UNSPSC y keywords para matching
de licitaciones. El campo `embedding` es interno del pipeline y
NO se expone en respuestas de API.
"""

from datetime import datetime
import enum
from typing import TYPE_CHECKING, Any
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.empresa import Empresa


class InteresTipo(str, enum.Enum):
    """Tipo de interés comercial. Refleja interes_tipo en schema.sql."""

    unspsc_segmento = "unspsc_segmento"
    unspsc_familia = "unspsc_familia"
    unspsc_clase = "unspsc_clase"
    unspsc_commodity = "unspsc_commodity"
    keyword = "keyword"
    ejemplo_codigo = "ejemplo_codigo"


class Interes(Base):
    """Interés comercial de una empresa: rubro UNSPSC o keyword."""

    __tablename__ = "intereses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
    )

    # El tipo ya existe en la BD como interes_tipo — create_type=False
    tipo: Mapped[InteresTipo] = mapped_column(
        Enum(InteresTipo, name="interes_tipo", create_type=False),
        nullable=False,
    )

    valor: Mapped[str] = mapped_column(String(255), nullable=False)

    prioridad: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=5,
        server_default="5",
    )

    # Campo interno del pipeline — NO exponer en respuestas de API
    embedding: Mapped[Any | None] = mapped_column(Vector(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relación con Empresa
    empresa: Mapped["Empresa"] = relationship(
        "Empresa",
        back_populates="intereses",
    )

    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "tipo",
            "valor",
            name="uq_intereses_empresa_tipo_valor",
        ),
        Index("idx_intereses_empresa", "empresa_id"),
        Index("idx_intereses_tipo_valor", "tipo", "valor"),
    )

    def __repr__(self) -> str:
        return (
            f"<Interes id={self.id} empresa_id={self.empresa_id} "
            f"tipo={self.tipo} valor={self.valor!r}>"
        )
