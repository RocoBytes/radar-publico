"""Modelo SQLAlchemy para la tabla empresas.

Empresa proveedora del Estado. Relación 1:1 con Usuario.
Un usuario = una empresa (v1). Multi-usuario llega en v2.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EmpresaTamano

if TYPE_CHECKING:
    from app.models.ticket import TicketApi
    from app.models.usuario import Usuario


class Empresa(Base):
    """Empresa proveedora. Asociada 1:1 a un Usuario de rol proveedor."""

    __tablename__ = "empresas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )

    # FK a usuarios — relación 1:1
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Datos de la empresa
    rut: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_fantasia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    giros: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )
    tamano: Mapped[EmpresaTamano | None] = mapped_column(
        Enum(EmpresaTamano, name="empresa_tamano", create_type=False), nullable=True
    )
    ano_fundacion: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    numero_empleados: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cobertura geográfica (arrays de texto — catálogos cerrados)
    regiones_operacion: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
    )
    comunas_operacion: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )

    # Flags de perfil
    sello_empresa_mujer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    inscrito_chileproveedores: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    certificaciones: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="'[]'::jsonb"
    )

    # Contacto
    contacto_telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    contacto_telefono_verificado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    contacto_direccion: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Estado del onboarding
    onboarding_completado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relaciones
    usuario: Mapped["Usuario"] = relationship(
        "Usuario",
        back_populates="empresa",
    )
    ticket: Mapped["TicketApi | None"] = relationship(
        "TicketApi",
        back_populates="empresa",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_empresas_rut", "rut"),
        Index("idx_empresas_usuario_id", "usuario_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Empresa id={self.id} rut={self.rut!r} "
            f"razon_social={self.razon_social!r}>"
        )
