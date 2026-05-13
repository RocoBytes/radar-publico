"""Modelos SQLAlchemy de solo lectura para catálogos geográficos y UNSPSC.

Estas tablas se cargan una sola vez vía seed y no se modifican desde la app.
Reflejan exactamente schema.sql — sección de catálogos.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Unspsc(Base):
    """Catálogo UNSPSC v14 jerárquico (segmento/familia/clase/commodity).

    Niveles:
        1 = segmento (2 dígitos)
        2 = familia  (4 dígitos)
        3 = clase    (6 dígitos)
        4 = commodity (8 dígitos)
    """

    __tablename__ = "unspsc_codigos"

    codigo: Mapped[str] = mapped_column(String(8), primary_key=True)
    nombre_es: Mapped[str] = mapped_column(String(255), nullable=False)
    descripcion_es: Mapped[str | None] = mapped_column(String, nullable=True)
    nivel: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    segmento: Mapped[str | None] = mapped_column(String(2), nullable=True)
    familia: Mapped[str | None] = mapped_column(String(4), nullable=True)
    clase: Mapped[str | None] = mapped_column(String(6), nullable=True)
    parent_codigo: Mapped[str | None] = mapped_column(
        String(8),
        ForeignKey("unspsc_codigos.codigo"),
        nullable=True,
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Auto-referencia jerárquica
    hijos: Mapped[list["Unspsc"]] = relationship(
        "Unspsc",
        foreign_keys=[parent_codigo],
        back_populates="padre",
        lazy="noload",
    )
    padre: Mapped["Unspsc | None"] = relationship(
        "Unspsc",
        foreign_keys=[parent_codigo],
        back_populates="hijos",
        remote_side=[codigo],
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<Unspsc codigo={self.codigo!r} nivel={self.nivel}"
            f" nombre={self.nombre_es!r}>"
        )


class Region(Base):
    """Región administrativa de Chile según codificación INE/SUBDERE."""

    __tablename__ = "regiones"

    codigo: Mapped[str] = mapped_column(String(10), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    nombre_corto: Mapped[str | None] = mapped_column(String(50), nullable=True)
    orden: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Relación hacia comunas
    comunas: Mapped[list["Comuna"]] = relationship(
        "Comuna",
        back_populates="region",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Region codigo={self.codigo!r} nombre={self.nombre!r}>"


class Comuna(Base):
    """Comuna de Chile. Cada una pertenece a una región."""

    __tablename__ = "comunas"

    codigo: Mapped[str] = mapped_column(String(10), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    region_codigo: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("regiones.codigo"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    region: Mapped["Region"] = relationship(
        "Region",
        back_populates="comunas",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Comuna codigo={self.codigo!r} nombre={self.nombre!r}>"
