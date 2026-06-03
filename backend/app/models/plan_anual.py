"""Modelo SQLAlchemy para la tabla plan_anual_lineas.

El plan anual de compras es publicado por cada organismo en Mercado Público
y anticipa las licitaciones que planean emitir durante el año.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import PlanAnualStatus


class PlanAnualLinea(Base):
    """Línea del plan anual de compras de un organismo."""

    __tablename__ = "plan_anual_lineas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )

    ano: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    codigo_organismo: Mapped[int] = mapped_column(
        ForeignKey("organismos.codigo_organismo", ondelete="RESTRICT"),
        nullable=False,
    )

    descripcion: Mapped[str] = mapped_column(Text, nullable=False)

    unspsc_codigo: Mapped[str | None] = mapped_column(
        String(8),
        ForeignKey("unspsc_codigos.codigo", ondelete="SET NULL"),
        nullable=True,
    )
    unspsc_nombre: Mapped[str | None] = mapped_column(String(500), nullable=True)

    monto_estimado: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    moneda: Mapped[str | None] = mapped_column(
        String(10), nullable=True, server_default="'CLP'"
    )

    # CHECK (mes_estimado BETWEEN 1 AND 12) — constraint en la BD, no en el ORM
    mes_estimado: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    modalidad: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # plan_anual_status existe en la BD como tipo ENUM — create_type=False
    status: Mapped[PlanAnualStatus] = mapped_column(
        Enum(PlanAnualStatus, name="plan_anual_status", create_type=False),
        nullable=False,
        default=PlanAnualStatus.planificada,
        server_default="'planificada'",
    )

    licitacion_codigo: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("licitaciones.codigo", ondelete="SET NULL"),
        nullable=True,
    )

    # tsvector generado por trigger en la BD — solo lectura desde el ORM
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR, nullable=True)

    # vector(1024) — Voyage AI embeddings
    embedding: Mapped[Any | None] = mapped_column(Vector(1024), nullable=True)

    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        Index("idx_plan_organismo_ano", "codigo_organismo", "ano"),
        Index("idx_plan_unspsc", "unspsc_codigo"),
        Index("idx_plan_status", "status"),
        # Los índices GIN (tsvector) y HNSW (vector) se crean en la migración
        # con op.execute() porque Alembic no los soporta nativamente.
    )

    def __repr__(self) -> str:
        return (
            f"<PlanAnualLinea id={self.id} ano={self.ano}"
            f" organismo={self.codigo_organismo} status={self.status}>"
        )
