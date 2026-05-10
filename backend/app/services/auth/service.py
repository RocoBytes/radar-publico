"""Servicio de autenticación.

Toda la lógica de sesión, tokens y recuperación de contraseña.
Sin PII en logs (regla #12) — se loggea user_id, no email.
"""

from datetime import UTC, datetime, timedelta
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_reset_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.enums import UserStatus
from app.models.eventos_auditoria import AuditAction
from app.models.password_reset import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.usuario import Usuario
from app.services.auth.audit import log_event
from app.services.auth.exceptions import (
    AccountLockedError,
    AccountSuspendedError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.services.email import sender as email_sender
from app.services.email.templates import password_changed as tpl_changed
from app.services.email.templates import password_reset as tpl_reset

logger = structlog.get_logger()

_MAX_ATTEMPTS = 5
_LOCKOUT_MINUTES = 30


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def login(
        self,
        email: str,
        password: str,
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[str, str, bool]:
        """Autentica. Retorna (access_token, refresh_token, must_change_password).

        Raises:
            InvalidCredentialsError: credenciales incorrectas (mensaje genérico).
            AccountLockedError: cuenta bloqueada temporalmente.
            AccountSuspendedError: cuenta suspendida.
        """
        result = await self._db.execute(
            select(Usuario).where(Usuario.email == email, Usuario.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()

        # Mensaje genérico en todos los casos de fallo (regla #4)
        if user is None:
            raise InvalidCredentialsError

        if user.status == UserStatus.suspended:
            raise AccountSuspendedError

        now = datetime.now(UTC)

        if user.locked_until and user.locked_until > now:
            remaining = int((user.locked_until - now).total_seconds())
            raise AccountLockedError(retry_after_seconds=remaining)

        if not verify_password(password, user.password_hash):
            new_attempts = user.failed_login_attempts + 1
            update_values: dict[str, object] = {"failed_login_attempts": new_attempts}

            if new_attempts >= _MAX_ATTEMPTS:
                update_values["locked_until"] = now + timedelta(
                    minutes=_LOCKOUT_MINUTES
                )
                logger.warning("auth.account.locked", user_id=str(user.id))

            await self._db.execute(
                update(Usuario).where(Usuario.id == user.id).values(**update_values)
            )
            await log_event(
                self._db,
                AuditAction.LOGIN_FAILED,
                usuario_id=user.id,
                ip=ip,
                user_agent=user_agent,
            )
            await self._db.commit()
            raise InvalidCredentialsError

        # Login exitoso — resetear contadores y emitir tokens
        access_token = create_access_token(str(user.id))
        refresh_plain, refresh_hash = create_refresh_token()

        rt = RefreshToken(
            usuario_id=user.id,
            token_hash=refresh_hash,
            ip_address=ip,
            user_agent=user_agent,
            expires_at=now + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
        self._db.add(rt)

        await self._db.execute(
            update(Usuario)
            .where(Usuario.id == user.id)
            .values(
                failed_login_attempts=0,
                locked_until=None,
                last_login_at=now,
            )
        )
        await log_event(
            self._db,
            AuditAction.LOGIN_OK,
            usuario_id=user.id,
            ip=ip,
            user_agent=user_agent,
        )
        await self._db.commit()

        logger.info("auth.login.success", user_id=str(user.id))
        return access_token, refresh_plain, user.must_change_password

    async def logout(self, refresh_plaintext: str) -> None:
        """Revoca el refresh token específico."""
        token_hash = hash_token(refresh_plaintext)
        result = await self._db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revocado_at.is_(None),
            )
        )
        rt = result.scalar_one_or_none()
        if rt is not None:
            rt.revocado_at = datetime.now(UTC)
            await log_event(
                self._db,
                AuditAction.LOGOUT,
                usuario_id=rt.usuario_id,
            )
            await self._db.commit()

    async def refresh(
        self,
        refresh_plaintext: str,
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[str, str]:
        """Rota el refresh token. Retorna (new_access_token, new_refresh_token).

        Raises:
            InvalidTokenError: token revocado, expirado o inexistente.
        """
        token_hash = hash_token(refresh_plaintext)
        now = datetime.now(UTC)

        result = await self._db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        rt = result.scalar_one_or_none()

        if rt is None or rt.revocado_at is not None or rt.expires_at <= now:
            raise InvalidTokenError

        # Rotar: revocar viejo y emitir nuevo par
        rt.revocado_at = now

        new_access = create_access_token(str(rt.usuario_id))
        new_plain, new_hash = create_refresh_token()

        new_rt = RefreshToken(
            usuario_id=rt.usuario_id,
            token_hash=new_hash,
            ip_address=ip,
            user_agent=user_agent,
            expires_at=now + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
        self._db.add(new_rt)

        await log_event(
            self._db,
            AuditAction.TOKEN_REFRESHED,
            usuario_id=rt.usuario_id,
            ip=ip,
        )
        await self._db.commit()

        return new_access, new_plain

    async def change_password(
        self,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str,
        current_refresh_hash: str,
    ) -> None:
        """Cambia contraseña. Revoca todos los refresh tokens excepto el actual.

        Raises:
            InvalidCredentialsError: contraseña actual incorrecta.
        """
        result = await self._db.execute(select(Usuario).where(Usuario.id == user_id))
        user = result.scalar_one()

        if not verify_password(current_password, user.password_hash):
            raise InvalidCredentialsError

        user.password_hash = hash_password(new_password)
        user.must_change_password = False

        # Revocar todos los refresh tokens excepto el actual
        now = datetime.now(UTC)
        tokens_result = await self._db.execute(
            select(RefreshToken).where(
                RefreshToken.usuario_id == user_id,
                RefreshToken.revocado_at.is_(None),
                RefreshToken.token_hash != current_refresh_hash,
            )
        )
        for rt in tokens_result.scalars().all():
            rt.revocado_at = now

        await log_event(
            self._db,
            AuditAction.PASSWORD_CHANGED,
            usuario_id=user_id,
        )
        await self._db.commit()

        subject, html, text = tpl_changed.render()
        await email_sender.send_email(user.email, subject, html, text)
        logger.info("auth.password.changed", user_id=str(user_id))

    async def forgot_password(self, email: str, ip: str | None) -> None:
        """Inicia recuperación. Respuesta siempre igual (anti-enumeración)."""
        result = await self._db.execute(
            select(Usuario).where(Usuario.email == email, Usuario.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()

        if user is None:
            return

        plain, token_hash = generate_reset_token()
        now = datetime.now(UTC)

        prt = PasswordResetToken(
            usuario_id=user.id,
            token_hash=token_hash,
            expires_at=now
            + timedelta(minutes=settings.password_reset_token_expire_minutes),
        )
        self._db.add(prt)

        await log_event(
            self._db,
            AuditAction.PASSWORD_RESET_REQUESTED,
            usuario_id=user.id,
            ip=ip,
        )
        await self._db.commit()

        reset_url = f"https://radarpublico.cl/reset-password?token={plain}"
        subject, html, text = tpl_reset.render(reset_url)
        await email_sender.send_email(user.email, subject, html, text)

    async def reset_password(self, token_plaintext: str, new_password: str) -> None:
        """Completa el reset. El token se usa una sola vez.

        Raises:
            InvalidTokenError: token inválido, expirado o ya usado.
        """
        token_hash = hash_token(token_plaintext)
        now = datetime.now(UTC)

        result = await self._db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
        )
        prt = result.scalar_one_or_none()

        if prt is None or prt.usado_at is not None or prt.expires_at <= now:
            raise InvalidTokenError

        user_result = await self._db.execute(
            select(Usuario).where(Usuario.id == prt.usuario_id)
        )
        user = user_result.scalar_one()

        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        prt.usado_at = now

        # Revocar todos los refresh tokens del usuario
        tokens_result = await self._db.execute(
            select(RefreshToken).where(
                RefreshToken.usuario_id == user.id,
                RefreshToken.revocado_at.is_(None),
            )
        )
        for rt in tokens_result.scalars().all():
            rt.revocado_at = now

        await log_event(
            self._db,
            AuditAction.PASSWORD_RESET_COMPLETED,
            usuario_id=user.id,
        )
        await self._db.commit()

        logger.info("auth.password.reset.completed", user_id=str(user.id))
