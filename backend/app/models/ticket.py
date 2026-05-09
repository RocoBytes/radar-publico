"""Modelo SQLAlchemy para la tabla tickets_api.

Regla de oro #2: ticket_cifrado NUNCA se expone fuera de este modelo.
El descifrado ocurre solo en memoria en services/chilecompra/client.py.
"""

from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import TicketStatus

if TYPE_CHECKING:
    from app.models.empresa import Empresa
    from app.models.usuario import Usuario


class TicketApi(Base):
    """Ticket de acceso a la API de ChileCompra, cifrado con AES-256-GCM."""

    __tablename__ = "tickets_api"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )

    # FK a empresa — 1:1
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # El ticket en claro JAMÁS se almacena aquí
    ticket_cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    # Solo los últimos 4 chars para mostrar en UI sin exponer el secreto
    ticket_ultimos_4: Mapped[str] = mapped_column(String(4), nullable=False)

    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status", create_type=False),
        nullable=False,
        default=TicketStatus.pending,
        server_default="pending",
    )
    cuota_diaria_max: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10000, server_default="10000"
    )

    # Trazabilidad: quién cargó el ticket
    cargado_por_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    cargado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Estado de salud del ticket
    ultima_validacion_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ultimo_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relaciones
    empresa: Mapped["Empresa"] = relationship(
        "Empresa",
        back_populates="ticket",
    )
    cargado_por: Mapped["Usuario | None"] = relationship(
        "Usuario",
        foreign_keys=[cargado_por_admin_id],
    )

    __table_args__ = (Index("idx_tickets_status", "status"),)

    def __repr__(self) -> str:
        return (
            f"<TicketApi id={self.id} empresa_id={self.empresa_id} "
            f"status={self.status} ultimos_4=***{self.ticket_ultimos_4}>"
        )
