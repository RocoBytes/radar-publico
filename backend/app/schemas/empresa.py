"""Schemas Pydantic para los endpoints de empresa.

EmpresaResponse expone los campos públicos del perfil.
EmpresaUpdateRequest limita los campos editables — rut, razon_social
y usuario_id son gestionados por el admin y no se aceptan en PATCH.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from typing import Any
import uuid  # noqa: TCH003

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EmpresaTamano  # noqa: TCH001


class EmpresaResponse(BaseModel):
    """Perfil público de la empresa del usuario autenticado."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rut: str
    razon_social: str
    nombre_fantasia: str | None
    giros: list[str] | None
    tamano: EmpresaTamano | None
    ano_fundacion: int | None
    numero_empleados: int | None
    regiones_operacion: list[str]
    comunas_operacion: list[str] | None
    sello_empresa_mujer: bool
    inscrito_chileproveedores: bool
    certificaciones: list[dict[str, Any]]
    contacto_telefono: str | None
    contacto_direccion: str | None
    onboarding_completado: bool
    created_at: datetime
    updated_at: datetime


class EmpresaUpdateRequest(BaseModel):
    """Campos editables de la empresa. Todos opcionales (PATCH parcial).

    Campos NO editables por el usuario: rut, razon_social, usuario_id.
    Esos los gestiona el admin.
    """

    model_config = ConfigDict(from_attributes=True)

    nombre_fantasia: str | None = None
    giros: list[str] | None = None
    tamano: EmpresaTamano | None = None
    ano_fundacion: int | None = Field(default=None, ge=1900, le=2100)
    numero_empleados: int | None = Field(default=None, ge=0)
    regiones_operacion: list[str] | None = None
    comunas_operacion: list[str] | None = None
    sello_empresa_mujer: bool | None = None
    inscrito_chileproveedores: bool | None = None
    certificaciones: list[dict[str, Any]] | None = None
    contacto_telefono: str | None = None
    contacto_direccion: str | None = None
    onboarding_completado: bool | None = None
