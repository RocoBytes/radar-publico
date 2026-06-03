"""Modelos SQLAlchemy para el pipeline de seguimiento de licitaciones.

Tablas cubiertas:
- pipeline_items: seguimiento de una licitación por una empresa
- pipeline_notas: notas textuales asociadas a un pipeline_item
- pipeline_checklist_items: checklist documental por pipeline_item
- pipeline_archivos: archivos adjuntos por pipeline_item
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    ChecklistItemEstado,
    ChecklistItemOrigen,
    LicitacionEstado,
    PipelineEstado,
)

if TYPE_CHECKING:
    from app.models.empresa import Empresa
    from app.models.licitacion import Licitacion
    from app.models.radar import Radar


class PipelineItem(Base):
    """Seguimiento de una licitación en el pipeline de una empresa.

    UNIQUE(empresa_id, licitacion_codigo) — cada empresa puede tener
    como máximo un ítem de pipeline por licitación.
    """

    __tablename__ = "pipeline_items"

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

    licitacion_codigo: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("licitaciones.codigo", ondelete="CASCADE"),
        nullable=False,
    )

    # pipeline_estado ya existe en la BD — create_type=False
    estado: Mapped[PipelineEstado] = mapped_column(
        Enum(PipelineEstado, name="pipeline_estado", create_type=False),
        nullable=False,
        default=PipelineEstado.nueva,
        server_default="'nueva'",
    )

    score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    score_justificacion: Mapped[Any | None] = mapped_column(JSONB, nullable=True)

    razon_descarte: Mapped[str | None] = mapped_column(Text, nullable=True)
    monto_postulado: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    resultado_observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)

    detected_by_radar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("radares.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="pipeline_items")
    licitacion: Mapped["Licitacion"] = relationship("Licitacion", back_populates="pipeline_items")
    radar: Mapped["Radar | None"] = relationship(
        "Radar",
        back_populates="pipeline_items",
        foreign_keys=[detected_by_radar_id],
    )
    notas: Mapped[list["PipelineNota"]] = relationship(
        "PipelineNota",
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="PipelineNota.created_at",
    )

    # Campo agregado en migración 20260603_1030:
    # registra el último estado de ChileCompra notificado para este ítem.
    # NULL hasta la primera alerta de cambio de estado externo.
    ultimo_estado_licitacion: Mapped[LicitacionEstado | None] = mapped_column(
        Enum(LicitacionEstado, name="licitacion_estado", create_type=False),
        nullable=True,
    )

    # Relación con checklist documental (migración 20260603_1000)
    # lazy="noload": el servicio consulta PipelineChecklistItem directamente;
    # cargar en cascade evita N+1 en listados donde el checklist no se renderiza.
    checklist_items: Mapped[list["PipelineChecklistItem"]] = relationship(
        "PipelineChecklistItem",
        back_populates="pipeline_item",
        cascade="all, delete-orphan",
        order_by="PipelineChecklistItem.orden",
        lazy="noload",
    )

    # lazy="noload" por la misma razón que checklist_items: los archivos
    # solo se cargan cuando el servicio los necesita explícitamente.
    archivos: Mapped[list["PipelineArchivo"]] = relationship(
        "PipelineArchivo",
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="PipelineArchivo.created_at",
        lazy="noload",
    )

    __table_args__ = (
        # Nombre auto-generado por PostgreSQL (UNIQUE sin nombre en schema.sql)
        UniqueConstraint(
            "empresa_id",
            "licitacion_codigo",
            name="pipeline_items_empresa_id_licitacion_codigo_key",
        ),
        Index("idx_pipeline_empresa_estado", "empresa_id", "estado"),
        Index("idx_pipeline_licitacion", "licitacion_codigo"),
    )

    def __repr__(self) -> str:
        return (
            f"<PipelineItem id={self.id} licitacion={self.licitacion_codigo!r}"
            f" estado={self.estado}>"
        )


class PipelineNota(Base):
    """Nota textual asociada a un ítem del pipeline."""

    __tablename__ = "pipeline_notas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )

    pipeline_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_items.id", ondelete="CASCADE"),
        nullable=False,
    )

    contenido: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    item: Mapped["PipelineItem"] = relationship("PipelineItem", back_populates="notas")

    __table_args__ = (Index("idx_notas_item", "pipeline_item_id", text("created_at DESC")),)

    def __repr__(self) -> str:
        return f"<PipelineNota id={self.id} item_id={self.pipeline_item_id}>"


class PipelineChecklistItem(Base):
    """Ítem del checklist documental asociado a un pipeline_item.

    Representa un documento o requisito que el proveedor debe preparar
    para postular a una licitación. Puede ser generado por IA a partir
    del análisis de bases (origen='ia_generado') o creado manualmente.

    Invariante: un ítem IA no puede duplicarse por bootstrap (índice único parcial
    uq_checklist_ia_dedup en (pipeline_item_id, lower(nombre)) WHERE origen='ia_generado').
    """

    __tablename__ = "pipeline_checklist_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    pipeline_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    obligatorio: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
    )
    estado: Mapped[ChecklistItemEstado] = mapped_column(
        Enum(ChecklistItemEstado, name="checklist_item_estado", create_type=False),
        nullable=False,
        default=ChecklistItemEstado.pendiente,
        server_default="'pendiente'",
    )
    origen: Mapped[ChecklistItemOrigen] = mapped_column(
        Enum(ChecklistItemOrigen, name="checklist_item_origen", create_type=False),
        nullable=False,
    )
    orden: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default="0",
        default=0,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    pipeline_item: Mapped["PipelineItem"] = relationship(
        "PipelineItem",
        back_populates="checklist_items",
    )

    __table_args__ = (Index("idx_checklist_pipeline_item", "pipeline_item_id"),)

    def __repr__(self) -> str:
        return (
            f"<PipelineChecklistItem id={self.id}" f" nombre={self.nombre!r} estado={self.estado}>"
        )


class PipelineArchivo(Base):
    """Archivo adjunto asociado a un ítem del pipeline.

    Almacenado en Cloudflare R2 (compatible S3).
    storage_path es la ruta relativa al bucket — nunca una URL pública.
    """

    __tablename__ = "pipeline_archivos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )

    pipeline_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_items.id", ondelete="CASCADE"),
        nullable=False,
    )

    nombre_original: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tamano_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    item: Mapped["PipelineItem"] = relationship("PipelineItem", back_populates="archivos")

    __table_args__ = (Index("idx_archivos_pipeline_item", "pipeline_item_id"),)

    def __repr__(self) -> str:
        return (
            f"<PipelineArchivo id={self.id}"
            f" nombre={self.nombre_original!r} item_id={self.pipeline_item_id}>"
        )
