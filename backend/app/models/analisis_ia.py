"""Modelos SQLAlchemy para los módulos de IA de Radar Público.

Tablas cubiertas:
- analisis_bases: resultado del análisis LLM de las bases técnicas de una licitación.
- borradores_propuesta: borrador de propuesta técnica generado por IA por empresa.

El análisis de bases es por licitación (objetivo, igual para todos los clientes).
El borrador es por empresa (usa el perfil de la empresa para personalizar).
"""

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AnalisisStatus


class AnalisisBases(Base):
    """Análisis LLM de las bases técnicas de una licitación.

    Generado por la tarea Celery analizar_bases_licitacion, encadenada al
    final del pipeline PDF (marcar_procesada → analizar_bases_licitacion).

    El análisis es objetivo y compartido entre todos los clientes que ven
    la misma licitación. La evaluación de cumplimiento por empresa (✅/⚠️/❌)
    es una capa de presentación calculada en tiempo de consulta.
    """

    __tablename__ = "analisis_bases"
    __table_args__ = (
        UniqueConstraint("licitacion_codigo", "version", name="uq_analisis_licitacion_version"),
    )

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
    version: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    status: Mapped[AnalisisStatus] = mapped_column(
        Enum(AnalisisStatus, name="analisis_status", create_type=False),
        nullable=False,
        server_default="pendiente",
    )
    requisitos_tecnicos: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    criterios_extraidos: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    documentos_obligatorios: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    plazos_clave: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    restricciones: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    resumen_ejecutivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    modelo_usado: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    tokens_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_mensaje: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class BorradorPropuesta(Base):
    """Borrador de propuesta técnica generado por IA para una empresa.

    Depende de AnalisisBases: no se puede generar un borrador sin análisis previo.
    El borrador usa el perfil de la empresa (giros, certificaciones, experiencia)
    para personalizar el contenido.

    El contenido se guarda en `secciones` como JSONB para permitir edición
    parcial por sección desde el frontend sin reemplazar el documento completo.
    """

    __tablename__ = "borradores_propuesta"
    __table_args__ = (
        UniqueConstraint(
            "licitacion_codigo",
            "empresa_id",
            "version",
            name="uq_borrador_licitacion_empresa_version",
        ),
    )

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
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analisis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analisis_bases.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    status: Mapped[AnalisisStatus] = mapped_column(
        Enum(AnalisisStatus, name="analisis_status", create_type=False),
        nullable=False,
        server_default="pendiente",
    )
    titulo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    secciones: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    documentos_pendientes: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    notas_revision: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    modelo_usado: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    tokens_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_mensaje: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
