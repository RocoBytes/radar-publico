"""Endpoints de autenticación — Epic 2 (US-2.1 a US-2.4).

Rate limiting (regla #6):
  POST /login        → 5 req / 15 min por IP
  POST /forgot-password → 3 req / 1 hora por IP
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
import structlog

from app.api.deps import CurrentUser, DbDep, get_request_ip
from app.core import rate_limit
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    ResetPasswordRequest,
    UserMe,
)
from app.services.auth.exceptions import (
    AccountLockedError,
    AccountSuspendedError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.services.auth.service import AuthService

logger = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["autenticación"])

IpDep = Annotated[str, Depends(get_request_ip)]


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: DbDep,
    ip: IpDep,
) -> LoginResponse:
    rl = await rate_limit.hit(f"login:{ip}", limit=5, window_seconds=900)
    if not rl.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Intentá de nuevo más tarde.",
            headers={"Retry-After": str(rl.retry_after)},
        )

    svc = AuthService(db)
    try:
        access, refresh, must_change = await svc.login(
            email=str(body.email),
            password=body.password,
            ip=ip,
            user_agent=request.headers.get("User-Agent"),
        )
    except (InvalidCredentialsError, AccountSuspendedError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        ) from None
    except AccountLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

    return LoginResponse(
        access_token=access,
        refresh_token=refresh,
        must_change_password=must_change,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    db: DbDep,
) -> None:
    await AuthService(db).logout(body.refresh_token)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    body: RefreshRequest,
    request: Request,
    db: DbDep,
    ip: IpDep,
) -> RefreshResponse:
    try:
        new_access, new_refresh = await AuthService(db).refresh(
            refresh_plaintext=body.refresh_token,
            ip=ip,
            user_agent=request.headers.get("User-Agent"),
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        ) from None
    return RefreshResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser,
    db: DbDep,
    # El refresh hash actual se pasa para NO revocarlo durante el cambio de pass
    current_refresh: str = Cookie(default=""),
) -> None:
    from app.core.security import hash_token

    try:
        await AuthService(db).change_password(
            user_id=current_user.id,
            current_password=body.current_password,
            new_password=body.new_password,
            current_refresh_hash=hash_token(current_refresh) if current_refresh else "",
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contraseña actual incorrecta",
        ) from None


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: DbDep,
    ip: IpDep,
) -> None:
    rl = await rate_limit.hit(f"forgot:{ip}", limit=3, window_seconds=3600)
    if not rl.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Intentá más tarde.",
            headers={"Retry-After": str(rl.retry_after)},
        )
    # Respuesta idéntica sin importar si el email existe (anti-enumeración)
    await AuthService(db).forgot_password(email=str(body.email), ip=ip)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    body: ResetPasswordRequest,
    db: DbDep,
) -> None:
    try:
        await AuthService(db).reset_password(
            token_plaintext=body.token,
            new_password=body.new_password,
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        ) from None


@router.get("/me", response_model=UserMe)
async def me(current_user: CurrentUser) -> UserMe:
    return UserMe.model_validate(current_user)
