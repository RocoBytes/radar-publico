"""Modelo SQLAlchemy para la tabla ordenes_compra.

Las órdenes de compra son emitidas por organismos a proveedores,
generalmente asociadas a una licitación adjudicada.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import OcEstado


class OrdenesCompra(Base):
    """Orden de compra emitida por un organismo a un proveedor."""

    __tablename__ = "ordenes_compra"

    codigo: Mapped[str] = mapped_column(String(50), primary_key=True)

    licitacion_codigo: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("licitaciones.codigo", ondelete="SET NULL"),
        nullable=True,
    )

    codigo_organismo: Mapped[int | None] = mapped_column(
        ForeignKey("organismos.codigo_organismo", ondelete="SET NULL"),
        nullable=True,
    )

    rut_proveedor: Mapped[str | None] = mapped_column(
        String(20),
        ForeignKey("proveedores.rut", ondelete="SET NULL"),
        nullable=True,
    )

    # oc_estado ya existe en la BD — create_type=False
    estado: Mapped[OcEstado] = mapped_column(
        Enum(OcEstado, name="oc_estado", create_type=False),
        nullable=False,
    )

    estado_codigo: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    nombre: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)

    moneda: Mapped[str | None] = mapped_column(
        String(10), nullable=True, server_default="'CLP'"
    )

    total_neto: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_impuestos: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)

    fecha_envio: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fecha_aceptacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        Index("idx_oc_licitacion", "licitacion_codigo"),
        Index("idx_oc_organismo", "codigo_organismo"),
        Index("idx_oc_proveedor", "rut_proveedor"),
        Index("idx_oc_fecha_envio", text("fecha_envio DESC")),
    )

    def __repr__(self) -> str:
        return (
            f"<OrdenesCompra codigo={self.codigo!r} estado={self.estado}"
            f" total={self.total}>"
        )
