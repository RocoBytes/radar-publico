"""Modelo SQLAlchemy para la tabla adjudicaciones.

Registra qué proveedor ganó cada licitación y por cuánto monto.
FK a licitaciones con CASCADE, a proveedores sin cascade (catálogo externo).
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.licitacion import Licitacion
    from app.models.proveedor import Proveedor


class Adjudicacion(Base):
    """Resultado de adjudicación de una licitación a un proveedor.

    Una licitación puede tener múltiples adjudicaciones (ítems adjudicados
    a distintos proveedores). PK uuid generado localmente.
    """

    __tablename__ = "adjudicaciones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    licitacion_codigo: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("licitaciones.codigo", ondelete="CASCADE"),
        nullable=False,
    )
    rut_proveedor: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("proveedores.rut"),
        nullable=False,
    )
    monto_adjudicado: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2),
        nullable=True,
    )
    fecha_adjudicacion: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relaciones
    licitacion: Mapped["Licitacion"] = relationship(
        "Licitacion",
        back_populates="adjudicaciones",
    )
    proveedor: Mapped["Proveedor"] = relationship(
        "Proveedor",
        back_populates="adjudicaciones",
    )

    __table_args__ = (
        Index("idx_adjudicaciones_licitacion", "licitacion_codigo"),
        Index("idx_adjudicaciones_proveedor", "rut_proveedor"),
        Index(
            "idx_adjudicaciones_fecha",
            "fecha_adjudicacion",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Adjudicacion id={self.id} licitacion={self.licitacion_codigo!r} "
            f"proveedor={self.rut_proveedor!r}>"
        )
