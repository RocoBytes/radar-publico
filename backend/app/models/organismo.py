"""Modelo SQLAlchemy para la tabla organismos.

Catálogo de organismos compradores del Mercado Público.
PK natural: codigo_organismo (int) — viene de la API de ChileCompra.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.licitacion import Licitacion


class Organismo(Base):
    """Organismo comprador del Estado. Sincronizado desde la API."""

    __tablename__ = "organismos"

    # PK natural de la API — NO uuid
    codigo_organismo: Mapped[int] = mapped_column(Integer, primary_key=True)

    rut: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nombre: Mapped[str] = mapped_column(String(500), nullable=False)
    ministerio: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    comuna: Mapped[str | None] = mapped_column(String(100), nullable=True)
    direccion: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relaciones
    licitaciones: Mapped[list["Licitacion"]] = relationship(
        "Licitacion", back_populates="organismo"
    )

    __table_args__ = (
        Index(
            "idx_organismos_nombre_trgm",
            "nombre",
            postgresql_using="gin",
            postgresql_ops={"nombre": "gin_trgm_ops"},
        ),
        Index("idx_organismos_region", "region"),
    )

    def __repr__(self) -> str:
        return f"<Organismo codigo={self.codigo_organismo} nombre={self.nombre!r}>"
