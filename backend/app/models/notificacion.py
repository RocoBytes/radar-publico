"""Modelo SQLAlchemy para la tabla notificaciones.

Notificaciones in-app, email y whatsapp generadas por el sistema para
las empresas proveedoras. Refleja fielmente la tabla notificaciones en schema.sql.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import NotifCanal, NotifStatus, NotifTipo

if TYPE_CHECKING:
    from app.models.empresa import Empresa


class Notificacion(Base):
    """Notificación generada para una empresa. Puede ser in_app, email o whatsapp."""

    __tablename__ = "notificaciones"

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

    tipo: Mapped[NotifTipo] = mapped_column(
        Enum(NotifTipo, name="notif_tipo", create_type=False),
        nullable=False,
    )

    canal: Mapped[NotifCanal] = mapped_column(
        Enum(NotifCanal, name="notif_canal", create_type=False),
        nullable=False,
    )

    status: Mapped[NotifStatus] = mapped_column(
        Enum(NotifStatus, name="notif_status", create_type=False),
        nullable=False,
        server_default="pendiente",
    )

    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    cuerpo: Mapped[str] = mapped_column(Text, nullable=False)

    datos: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="'{}'::jsonb"
    )

    licitacion_codigo: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("licitaciones.codigo", ondelete="SET NULL"),
        nullable=True,
    )

    radar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("radares.id", ondelete="SET NULL"),
        nullable=True,
    )

    programada_para: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    enviada_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    leida_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    error_mensaje: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relaciones
    empresa: Mapped["Empresa"] = relationship(
        "Empresa",
        back_populates="notificaciones",
    )

    __table_args__ = (
        Index("idx_notificaciones_empresa_id", "empresa_id"),
        Index("idx_notificaciones_status", "status"),
        Index("idx_notificaciones_canal", "canal"),
        Index("idx_notificaciones_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Notificacion id={self.id} tipo={self.tipo!r} "
            f"canal={self.canal!r} status={self.status!r}>"
        )
