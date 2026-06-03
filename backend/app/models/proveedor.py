"""Modelo SQLAlchemy para la tabla proveedores.

Catálogo de proveedores. PK natural: rut (string).
Sincronizado desde la API y desde Datos Abiertos.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.adjudicacion import Adjudicacion


class Proveedor(Base):
    """Proveedor del Estado registrado en ChileProveedores."""

    __tablename__ = "proveedores"

    # PK natural — RUT del proveedor
    rut: Mapped[str] = mapped_column(String(20), primary_key=True)

    razon_social: Mapped[str] = mapped_column(String(500), nullable=False)
    nombre_fantasia: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relaciones
    adjudicaciones: Mapped[list["Adjudicacion"]] = relationship(
        "Adjudicacion",
        back_populates="proveedor",
    )

    def __repr__(self) -> str:
        return f"<Proveedor rut={self.rut!r} razon_social={self.razon_social!r}>"
