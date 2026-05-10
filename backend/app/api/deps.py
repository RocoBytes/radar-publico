"""Dependencias reutilizables de FastAPI.

get_db, get_current_user, get_current_admin, require_password_change_completed,
get_request_ip.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import InvalidTokenError, decode_access_token
from app.db import session as _db_session
from app.models.enums import UserRole, UserStatus
from app.models.usuario import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _db_session.AsyncSessionLocal() as session:
        yield session


DbDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbDep,
) -> Usuario:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except InvalidTokenError:
        raise credentials_exception from None

    result = await db.execute(
        select(Usuario)
        .where(
            Usuario.id == payload.sub,
            Usuario.deleted_at.is_(None),
        )
        .options(selectinload(Usuario.empresa))  # evita lazy load en serialización
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if user.status != UserStatus.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta inactiva",
        )

    return user


CurrentUser = Annotated[Usuario, Depends(get_current_user)]


async def get_current_admin(current_user: CurrentUser) -> Usuario:
    if current_user.rol != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol admin",
        )
    return current_user


AdminUser = Annotated[Usuario, Depends(get_current_admin)]


async def require_password_change_completed(current_user: CurrentUser) -> Usuario:
    if current_user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debés cambiar tu contraseña antes de continuar",
        )
    return current_user


ActiveUser = Annotated[Usuario, Depends(require_password_change_completed)]


def get_request_ip(request: Request) -> str:
    """Extrae la IP del cliente. Respeta X-Forwarded-For solo en producción."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
