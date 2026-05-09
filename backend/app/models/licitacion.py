"""Modelos SQLAlchemy para licitaciones y entidades relacionadas.

Tablas cubiertas:
- licitaciones (tabla principal)
- licitacion_items (items con UNSPSC)
- criterios_evaluacion
- licitacion_fechas
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import FechaTipo, LicitacionEstado

if TYPE_CHECKING:
    from app.models.organismo import Organismo


class Licitacion(Base):
    """Licitación publicada en Mercado Público.

    PK: codigo (natural de la API, ej: '1509-5-L114') — permite upserts
    directos durante la sincronización sin lookups previos.
    """

    __tablename__ = "licitaciones"

    # PK natural — código de la API (NO uuid)
    codigo: Mapped[str] = mapped_column(String(50), primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    nombre: Mapped[str] = mapped_column(String(1000), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)

    # FK a organismos
    codigo_organismo: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("organismos.codigo_organismo", ondelete="SET NULL"),
        nullable=True,
    )
    codigo_unidad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unidad_compra: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rut_unidad: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Estado (enum interno + código numérico original de la API)
    # create_type=False — el tipo ya existe en schema.sql
    estado: Mapped[LicitacionEstado] = mapped_column(
        Enum(LicitacionEstado, name="licitacion_estado", create_type=False),
        nullable=False,
    )
    estado_codigo: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Clasificación
    tipo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    modalidad: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Monto
    moneda: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="CLP"
    )
    monto_estimado: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)

    # Contrato y renovabilidad
    es_renovable: Mapped[bool] = mapped_column(
        Boolean, nullable=True, server_default="false"
    )
    unidad_tiempo_contrato: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
    tiempo_contrato: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duracion_estimada_meses: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Fechas críticas (desnormalizadas aquí + normalizadas en licitacion_fechas)
    fecha_creacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fecha_publicacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fecha_cierre: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fecha_adjudicacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Campo derivado clave para el feed de renovaciones (Epic 9)
    fecha_estimada_termino_contrato: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Contacto
    contacto_nombre: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contacto_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contacto_telefono: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Payload crudo de la API — para reprocesar sin volver a consultar
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Búsqueda y similitud
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR, nullable=True)
    embedding: Mapped[Any | None] = mapped_column(Vector(1024), nullable=True)

    # Control del pipeline de ingesta
    hash_contenido: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detalle_sincronizado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    bases_descargadas_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    bases_procesadas_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relaciones
    organismo: Mapped["Organismo | None"] = relationship(
        "Organismo", back_populates="licitaciones"
    )
    items: Mapped[list["LicitacionItem"]] = relationship(
        "LicitacionItem", back_populates="licitacion", cascade="all, delete-orphan"
    )
    criterios: Mapped[list["CriterioEvaluacion"]] = relationship(
        "CriterioEvaluacion", back_populates="licitacion", cascade="all, delete-orphan"
    )
    fechas: Mapped[list["LicitacionFecha"]] = relationship(
        "LicitacionFecha", back_populates="licitacion", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_licitaciones_estado", "estado"),
        Index("idx_licitaciones_organismo", "codigo_organismo"),
        Index(
            "idx_licitaciones_fecha_cierre",
            "fecha_cierre",
            postgresql_where=text("estado = 'publicada'"),
        ),
        Index("idx_licitaciones_fecha_publicacion", text("fecha_publicacion DESC")),
        Index("idx_licitaciones_search", "search_vector", postgresql_using="gin"),
        Index(
            "idx_licitaciones_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "idx_licitaciones_renovacion",
            "fecha_estimada_termino_contrato",
            postgresql_where=text("es_renovable = true AND estado = 'adjudicada'"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Licitacion codigo={self.codigo!r} estado={self.estado}>"


class LicitacionItem(Base):
    """Item de una licitación con su clasificación UNSPSC."""

    __tablename__ = "licitacion_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    licitacion_codigo: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("licitaciones.codigo", ondelete="CASCADE"),
        nullable=False,
    )
    numero_item: Mapped[int] = mapped_column(Integer, nullable=False)
    categoria: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # CLAUDE.md §9: filtro por rubro se hace sobre unspsc_codigo del item
    unspsc_codigo: Mapped[str | None] = mapped_column(
        String(8),
        ForeignKey("unspsc_codigos.codigo", ondelete="SET NULL"),
        nullable=True,
    )
    unspsc_nombre: Mapped[str | None] = mapped_column(String(500), nullable=True)

    nombre_producto: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    cantidad: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    unidad: Mapped[str | None] = mapped_column(String(100), nullable=True)
    monto_unitario_estimado: Mapped[float | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    especificaciones: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relaciones
    licitacion: Mapped["Licitacion"] = relationship(
        "Licitacion", back_populates="items"
    )

    __table_args__ = (
        UniqueConstraint("licitacion_codigo", "numero_item"),
        Index("idx_items_licitacion", "licitacion_codigo"),
        Index("idx_items_unspsc", "unspsc_codigo"),
    )

    def __repr__(self) -> str:
        return (
            f"<LicitacionItem licitacion={self.licitacion_codigo!r} "
            f"item={self.numero_item}>"
        )


class CriterioEvaluacion(Base):
    """Criterio de evaluación de una licitación con su ponderación."""

    __tablename__ = "criterios_evaluacion"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    licitacion_codigo: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("licitaciones.codigo", ondelete="CASCADE"),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(500), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    ponderacion: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    tipo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    orden: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    licitacion: Mapped["Licitacion"] = relationship(
        "Licitacion", back_populates="criterios"
    )

    __table_args__ = (Index("idx_criterios_licitacion", "licitacion_codigo"),)

    def __repr__(self) -> str:
        return (
            f"<CriterioEvaluacion licitacion={self.licitacion_codigo!r} "
            f"nombre={self.nombre!r} ponderacion={self.ponderacion}>"
        )


class LicitacionFecha(Base):
    """Fechas del calendario de una licitación (normalizadas)."""

    __tablename__ = "licitacion_fechas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    licitacion_codigo: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("licitaciones.codigo", ondelete="CASCADE"),
        nullable=False,
    )
    tipo: Mapped[FechaTipo] = mapped_column(
        Enum(FechaTipo, name="fecha_tipo", create_type=False), nullable=False
    )
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    es_estimada: Mapped[bool] = mapped_column(
        Boolean, nullable=True, server_default="false"
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)

    licitacion: Mapped["Licitacion"] = relationship(
        "Licitacion", back_populates="fechas"
    )

    __table_args__ = (
        UniqueConstraint("licitacion_codigo", "tipo"),
        Index("idx_fechas_tipo_fecha", "tipo", "fecha"),
    )

    def __repr__(self) -> str:
        return (
            f"<LicitacionFecha licitacion={self.licitacion_codigo!r} "
            f"tipo={self.tipo} fecha={self.fecha}>"
        )
