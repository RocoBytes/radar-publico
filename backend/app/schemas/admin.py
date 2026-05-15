"""Schemas Pydantic v2 para el panel admin.

Regla #2: ticket_cifrado nunca aparece en ningún schema de respuesta.
"""

from datetime import datetime
import re
from typing import Literal
import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import TicketStatus, UserRole, UserStatus

_RUT_RE = re.compile(r"^\d{1,2}\.\d{3}\.\d{3}-[\dKk]$")


class CrearCuentaRequest(BaseModel):
    email: EmailStr
    rut: str = Field(..., description="Formato XX.XXX.XXX-Y")
    razon_social: str = Field(..., min_length=2, max_length=255)
    plan: str = Field(default="starter")

    @field_validator("rut")
    @classmethod
    def validar_rut(cls, v: str) -> str:
        if not _RUT_RE.match(v):
            raise ValueError(
                "RUT debe tener formato XX.XXX.XXX-Y (ej: 76.123.456-7)"
            )
        return v


class EmpresaResumen(BaseModel):
    rut: str
    razon_social: str
    tiene_ticket: bool

    model_config = {"from_attributes": True}


class CuentaResponse(BaseModel):
    id: uuid.UUID
    email: str
    rol: UserRole
    status: UserStatus
    must_change_password: bool
    created_at: datetime
    empresa: EmpresaResumen | None = None

    model_config = {"from_attributes": True}


class CuentaCreadaResponse(CuentaResponse):
    """Respuesta de creación — expone la contraseña temporal una sola vez."""

    temp_password: str


class CuentaListResponse(BaseModel):
    items: list[CuentaResponse]
    total: int
    page: int
    page_size: int


class CambiarEstadoRequest(BaseModel):
    accion: Literal["suspender", "reactivar"]


class CargarTicketRequest(BaseModel):
    ticket: str = Field(..., min_length=10, max_length=500)


class TicketResponse(BaseModel):
    id: uuid.UUID
    ultimos_4: str = Field(alias="ticket_ultimos_4")
    status: TicketStatus
    cargado_at: datetime | None = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class ImpersonacionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class TicketDiagnosticoResponse(BaseModel):
    tiene_ticket: bool
    ticket_ultimos_4: str | None = None
    ticket_status: str | None = None
    llamadas_hoy: int
    test_ok: bool | None = None
    test_error: str | None = None
    test_duracion_ms: int | None = None
