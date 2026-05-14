"""Modelos SQLAlchemy de solo lectura para catálogos geográficos y UNSPSC.

Estas tablas se cargan una sola vez vía seed y no se modifican desde la app.
Reflejan exactamente schema.sql — sección de catálogos.
"""

from sqlalchemy import ForeignKey, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Unspsc(Base):
    """Catálogo UNSPSC v14 jerárquico (segmento/familia/clase/commodity).

    nivel: 2=segmento, 4=familia, 6=clase, 8=commodity.
    """

    __tablename__ = "unspsc_codigos"

    codigo: Mapped[str] = mapped_column(String(8), primary_key=True)
    nivel: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    segmento: Mapped[str] = mapped_column(String(2), nullable=False)
    familia: Mapped[str | None] = mapped_column(String(4), nullable=True)
    clase: Mapped[str | None] = mapped_column(String(6), nullable=True)
    commodity: Mapped[str | None] = mapped_column(String(8), nullable=True)
    nombre_es: Mapped[str] = mapped_column(String(500), nullable=False)
    nombre_en: Mapped[str | None] = mapped_column(String(500), nullable=True)
    descripcion_es: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_codigo: Mapped[str | None] = mapped_column(
        String(8),
        ForeignKey("unspsc_codigos.codigo"),
        nullable=True,
    )

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
        return f"<Unspsc {self.codigo!r} nivel={self.nivel} {self.nombre_es!r}>"


class Region(Base):
    """Región administrativa de Chile según codificación INE/SUBDERE."""

    __tablename__ = "regiones"

    codigo: Mapped[str] = mapped_column(String(10), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    numero_romano: Mapped[str | None] = mapped_column(String(10), nullable=True)
    orden: Mapped[int | None] = mapped_column(SmallInteger, nullable=False)

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
    region_codigo: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("regiones.codigo"),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)

    region: Mapped["Region"] = relationship(
        "Region",
        back_populates="comunas",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Comuna codigo={self.codigo!r} nombre={self.nombre!r}>"
