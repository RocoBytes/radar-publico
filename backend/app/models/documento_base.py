"""Modelos SQLAlchemy para documentos de bases de licitaciones.

Tablas cubiertas:
- documentos_bases (documentos descargados desde el portal)
- documento_chunks  (chunks vectorizados para RAG — Sprint 5)
"""

from datetime import datetime
from typing import Any
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import DocumentoStatus, DocumentoTipo


class DocumentoBase(Base):
    """Documento adjunto de bases de una licitación.

    Ciclo de vida del campo status:
      pendiente  → descargado (esta fase)
      descargado → procesado  (fase de parseo PDF, Sprint 2 siguiente)
    """

    __tablename__ = "documentos_bases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    licitacion_codigo: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("licitaciones.codigo", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo: Mapped[DocumentoTipo] = mapped_column(
        Enum(DocumentoTipo, name="documento_tipo", create_type=False),
        nullable=False,
    )
    nombre_original: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url_origen: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_bucket: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tamano_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    num_paginas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[DocumentoStatus] = mapped_column(
        Enum(DocumentoStatus, name="documento_status", create_type=False),
        nullable=False,
        server_default="pendiente",
    )
    texto_extraido: Mapped[str | None] = mapped_column(Text, nullable=True)
    hash_contenido: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_mensaje: Mapped[str | None] = mapped_column(Text, nullable=True)
    descargado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    procesado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class DocumentoChunk(Base):
    """Chunk vectorizado de un documento de bases, para búsqueda semántica (RAG).

    Populated en la fase de embeddings (Sprint 2, siguiente a esta).
    El índice HNSW en 'embedding' ya existe en schema.sql.
    """

    __tablename__ = "documento_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    documento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documentos_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    licitacion_codigo: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("licitaciones.codigo", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_orden: Mapped[int] = mapped_column(Integer, nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    pagina_inicio: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pagina_fin: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[Any | None] = mapped_column(Vector(1024), nullable=True)
    # 'metadata' es nombre reservado en SA Declarative — se mapea explícitamente
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
