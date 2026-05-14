"""Modelo SQLAlchemy para la tabla radares.

Un radar es una búsqueda guardada con filtros JSON que dispara alertas
cuando aparecen licitaciones nuevas que coinciden con sus criterios.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.empresa import Empresa
    from app.models.pipeline import PipelineItem


class Radar(Base):
    """Búsqueda guardada de una empresa."""

    __tablename__ = "radares"

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

    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Filtros serializados: {"q": "...", "estado": "publicada", "unspsc_codigo": "73"}
    filtros: Mapped[Any] = mapped_column(JSONB, nullable=False)

    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    notif_canal: Mapped[str] = mapped_column(
        String(20), nullable=False, default="email", server_default="'email'"
    )
    notif_frecuencia: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="instantaneo",
        server_default="'instantaneo'",
    )
    notif_score_minimo: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, default=70, server_default="70"
    )

    ultima_ejecucion_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="radares")
    pipeline_items: Mapped[list["PipelineItem"]] = relationship(
        "PipelineItem",
        back_populates="radar",
        foreign_keys="PipelineItem.detected_by_radar_id",
    )

    __table_args__ = (Index("idx_radares_empresa_activo", "empresa_id", "activo"),)

    def __repr__(self) -> str:
        return f"<Radar id={self.id} nombre={self.nombre!r} activo={self.activo}>"
