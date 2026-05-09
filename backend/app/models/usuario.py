"""Modelo SQLAlchemy para la tabla usuarios.

Refleja exactamente schema.sql — sección 1 (Usuarios y Empresas).
La lógica de auth (bcrypt, JWT, must_change_password flow) va en
app/core/auth.py — tarea separada de Sprint 1.
"""

from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Enum, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import UserRole, UserStatus


class Usuario(Base):
    """Cuenta del sistema. Roles: admin (operador) y proveedor (cliente)."""

    __tablename__ = "usuarios"

    # Clave primaria
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )

    # Identificación y credenciales
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Rol y estado — create_type=False porque los tipos ya existen en schema.sql
    rol: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", create_type=False),
        nullable=False,
        default=UserRole.proveedor,
        server_default="proveedor",
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", create_type=False),
        nullable=False,
        default=UserStatus.pending_activation,
        server_default="pending_activation",
    )

    # Flags de seguridad (columnas puras — lógica en core/auth.py)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relación bidireccional con Empresa (1:1)
    empresa: Mapped["Empresa | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Empresa",
        back_populates="usuario",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "idx_usuarios_email",
            "email",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_usuarios_status",
            "status",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} email={self.email!r} rol={self.rol}>"
