"""DTOs de autenticación (request / response).

Validador de password reusable: mínimo 10 chars, mayúscula, minúscula y dígito.
"""

import re
import uuid

from pydantic import BaseModel, EmailStr, field_validator

from app.models.enums import UserRole

_PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{10,}$")


def _validate_password_strength(v: str) -> str:
    if not _PASSWORD_PATTERN.match(v):
        raise ValueError(
            "La contraseña debe tener al menos 10 caracteres, "
            "una mayúscula, una minúscula y un número."
        )
    return v


# ---------- Login ----------


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    must_change_password: bool


# ---------- Refresh ----------


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ---------- Change password ----------


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


# ---------- Forgot / Reset ----------


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


# ---------- Me ----------


class EmpresaBasica(BaseModel):
    id: uuid.UUID
    rut: str
    razon_social: str

    model_config = {"from_attributes": True}


class UserMe(BaseModel):
    id: uuid.UUID
    email: str
    rol: UserRole
    must_change_password: bool
    empresa: EmpresaBasica | None = None

    model_config = {"from_attributes": True}
