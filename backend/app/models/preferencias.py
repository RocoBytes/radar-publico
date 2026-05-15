"""Modelo SQLAlchemy para la tabla preferencias_notificaciones.

Preferencias de notificación por empresa: canales activos, frecuencia de email,
scores mínimos y tipos de notificación habilitados. Refleja fielmente la tabla
preferencias_notificaciones en schema.sql.
"""

from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.empresa import Empresa

_TIPOS_ACTIVOS_DEFAULT = (
    '["nueva_oportunidad","recordatorio_cierre","cambio_estado",'
    '"adjudicacion_postulacion","oportunidad_futura"]'
)


class PreferenciasNotificaciones(Base):
    """Preferencias de notificación de una empresa.

    Una fila por empresa (PK = empresa_id).
    """

    __tablename__ = "preferencias_notificaciones"

    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("empresas.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Canal email
    email_activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    # Mapeado como String(20) porque la BD usa varchar(20), no un tipo ENUM de PG
    email_frecuencia: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'instantaneo'")
    )
    email_score_minimo: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Canal WhatsApp
    whatsapp_activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    whatsapp_solo_criticas: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    whatsapp_score_minimo: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
    whatsapp_pausado_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Canal in-app
    in_app_activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    # Tipos habilitados
    tipos_activos: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text(f"'{_TIPOS_ACTIVOS_DEFAULT}'::jsonb"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relación
    empresa: Mapped["Empresa"] = relationship(
        "Empresa",
        back_populates="preferencias_notificaciones",
    )

    def __repr__(self) -> str:
        return (
            f"<PreferenciasNotificaciones empresa_id={self.empresa_id} "
            f"email={self.email_activo} whatsapp={self.whatsapp_activo}>"
        )
