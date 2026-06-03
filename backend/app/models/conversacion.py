"""Modelos SQLAlchemy para conversaciones IA sobre bases de licitaciones.

Tablas cubiertas:
- conversaciones_ia  (sesión de chat por empresa + licitación)
- conversacion_mensajes (mensajes individuales con citas y metadatos de uso)
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MensajeRol

if TYPE_CHECKING:
    from app.models.empresa import Empresa


class ConversacionIA(Base):
    """Sesión de chat IA entre una empresa y una licitación."""

    __tablename__ = "conversaciones_ia"

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

    licitacion_codigo: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("licitaciones.codigo", ondelete="CASCADE"),
        nullable=True,
    )

    titulo: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    # Relaciones
    mensajes: Mapped[list["ConversacionMensaje"]] = relationship(
        "ConversacionMensaje",
        back_populates="conversacion",
        lazy="noload",
    )

    empresa: Mapped["Empresa"] = relationship(
        "Empresa",
        back_populates=None,
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<ConversacionIA id={self.id} empresa_id={self.empresa_id} "
            f"licitacion={self.licitacion_codigo!r}>"
        )


class ConversacionMensaje(Base):
    """Mensaje individual dentro de una conversación IA."""

    __tablename__ = "conversacion_mensajes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )

    conversacion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversaciones_ia.id", ondelete="CASCADE"),
        nullable=False,
    )

    rol: Mapped[MensajeRol] = mapped_column(
        Enum(MensajeRol, name="mensaje_rol", create_type=False),
        nullable=False,
    )

    contenido: Mapped[str] = mapped_column(Text, nullable=False)

    citas: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
        server_default="'[]'::jsonb",
    )

    modelo_usado: Mapped[str | None] = mapped_column(String(50), nullable=True)

    tokens_input: Mapped[int | None] = mapped_column(nullable=True)

    tokens_output: Mapped[int | None] = mapped_column(nullable=True)

    costo_estimado: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relaciones
    conversacion: Mapped["ConversacionIA"] = relationship(
        "ConversacionIA",
        back_populates="mensajes",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<ConversacionMensaje id={self.id} rol={self.rol!r} "
            f"conversacion_id={self.conversacion_id}>"
        )
