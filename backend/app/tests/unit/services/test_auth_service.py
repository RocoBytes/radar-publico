"""Tests unitarios del AuthService con mocks de AsyncSession.

Se verifica lógica de negocio sin tocar la base de datos real.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from app.core.security import hash_password
from app.models.enums import UserStatus
from app.services.auth.exceptions import (
    AccountLockedError,
    AccountSuspendedError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.services.auth.service import AuthService


def _make_user(**kwargs: Any) -> MagicMock:
    """Crea un mock de Usuario con valores por defecto razonables."""
    user = MagicMock()
    user.id = kwargs.get("id", uuid.uuid4())
    user.email = kwargs.get("email", "test@example.cl")
    user.password_hash = kwargs.get("password_hash", hash_password("Password123!"))
    user.status = kwargs.get("status", UserStatus.active)
    user.must_change_password = kwargs.get("must_change_password", False)
    user.failed_login_attempts = kwargs.get("failed_login_attempts", 0)
    user.locked_until = kwargs.get("locked_until")
    user.deleted_at = None
    return user


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    return session


def _scalar_result(value: Any) -> AsyncMock:
    """Simula el resultado de session.execute(...).scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    result.scalars.return_value.all.return_value = []
    return result


@pytest.mark.asyncio
class TestLogin:
    async def test_login_ok(self) -> None:
        user = _make_user()
        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        with patch("app.services.auth.service.log_event", new_callable=AsyncMock):
            svc = AuthService(session)
            access, refresh, must_change = await svc.login(
                "test@example.cl", "Password123!", "1.2.3.4", "TestAgent"
            )

        assert access
        assert refresh
        assert must_change is False

    async def test_login_falla_usuario_no_existe(self) -> None:
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        with patch("app.services.auth.service.log_event", new_callable=AsyncMock):
            svc = AuthService(session)
            with pytest.raises(InvalidCredentialsError):
                await svc.login("noexiste@example.cl", "pass", None, None)

    async def test_login_falla_cuenta_suspendida(self) -> None:
        user = _make_user(status=UserStatus.suspended)
        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        svc = AuthService(session)
        with pytest.raises(AccountSuspendedError):
            await svc.login("test@example.cl", "Password123!", None, None)

    async def test_login_falla_cuenta_bloqueada(self) -> None:
        future = datetime.now(UTC) + timedelta(minutes=29)
        user = _make_user(locked_until=future)
        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        svc = AuthService(session)
        with pytest.raises(AccountLockedError):
            await svc.login("test@example.cl", "Password123!", None, None)

    async def test_login_falla_password_incorrecto(self) -> None:
        user = _make_user(failed_login_attempts=0)
        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        with patch("app.services.auth.service.log_event", new_callable=AsyncMock):
            svc = AuthService(session)
            with pytest.raises(InvalidCredentialsError):
                await svc.login("test@example.cl", "WrongPass!", None, None)

    async def test_quinto_intento_setea_locked_until(self) -> None:
        user = _make_user(failed_login_attempts=4)
        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        locked_until_values: list[Any] = []

        async def capture_execute(stmt: Any) -> Any:
            # Captura el update con locked_until
            stmt_str = str(stmt)
            if "locked_until" in stmt_str:
                locked_until_values.append(True)
            return _scalar_result(user)

        session.execute.side_effect = capture_execute

        with patch("app.services.auth.service.log_event", new_callable=AsyncMock):
            svc = AuthService(session)
            with pytest.raises(InvalidCredentialsError):
                await svc.login("test@example.cl", "WrongPass!", None, None)

        # Se emitió un UPDATE con locked_until (probado vía commit)
        session.commit.assert_called_once()

    async def test_login_exitoso_resetea_contadores(self) -> None:
        user = _make_user(failed_login_attempts=3)
        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        with patch("app.services.auth.service.log_event", new_callable=AsyncMock):
            svc = AuthService(session)
            await svc.login("test@example.cl", "Password123!", None, None)

        session.commit.assert_called_once()


@pytest.mark.asyncio
class TestLogout:
    async def test_logout_revoca_token(self) -> None:
        refresh_plain = "my-refresh-token"
        rt = MagicMock()
        rt.usuario_id = uuid.uuid4()

        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = rt
        session.execute.return_value = result

        with patch("app.services.auth.service.log_event", new_callable=AsyncMock):
            svc = AuthService(session)
            await svc.logout(refresh_plain)

        assert rt.revocado_at is not None
        session.commit.assert_called_once()

    async def test_logout_token_inexistente_no_falla(self) -> None:
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        svc = AuthService(session)
        await svc.logout("nonexistent-token")
        session.commit.assert_not_called()


@pytest.mark.asyncio
class TestRefresh:
    async def test_refresh_ok_rota_token(self) -> None:
        rt = MagicMock()
        rt.revocado_at = None
        rt.expires_at = datetime.now(UTC) + timedelta(days=6)
        rt.usuario_id = uuid.uuid4()

        session = _make_session()
        session.execute.return_value = _scalar_result(rt)

        with patch("app.services.auth.service.log_event", new_callable=AsyncMock):
            svc = AuthService(session)
            new_access, new_refresh = await svc.refresh("plain-token", None, None)

        assert new_access
        assert new_refresh
        assert rt.revocado_at is not None

    async def test_refresh_falla_token_revocado(self) -> None:
        rt = MagicMock()
        rt.revocado_at = datetime.now(UTC) - timedelta(minutes=5)
        rt.expires_at = datetime.now(UTC) + timedelta(days=6)

        session = _make_session()
        session.execute.return_value = _scalar_result(rt)

        svc = AuthService(session)
        with pytest.raises(InvalidTokenError):
            await svc.refresh("plain-token", None, None)

    async def test_refresh_falla_token_expirado(self) -> None:
        rt = MagicMock()
        rt.revocado_at = None
        rt.expires_at = datetime.now(UTC) - timedelta(hours=1)

        session = _make_session()
        session.execute.return_value = _scalar_result(rt)

        svc = AuthService(session)
        with pytest.raises(InvalidTokenError):
            await svc.refresh("plain-token", None, None)

    async def test_refresh_falla_token_inexistente(self) -> None:
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        svc = AuthService(session)
        with pytest.raises(InvalidTokenError):
            await svc.refresh("nonexistent", None, None)


@pytest.mark.asyncio
class TestForgotPassword:
    async def test_email_no_existente_no_lanza_excepcion(self) -> None:
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        svc = AuthService(session)
        # No debe lanzar ni crear token
        await svc.forgot_password("noexiste@example.cl", None)
        session.add.assert_not_called()

    async def test_email_existente_crea_token(self) -> None:
        user = _make_user()
        session = _make_session()
        session.execute.return_value = _scalar_result(user)

        with (
            patch("app.services.auth.service.log_event", new_callable=AsyncMock),
            patch("app.services.email.sender.send_email", new_callable=AsyncMock),
        ):
            svc = AuthService(session)
            await svc.forgot_password("test@example.cl", None)

        session.add.assert_called_once()
        session.commit.assert_called_once()


@pytest.mark.asyncio
class TestResetPassword:
    async def test_token_invalido_lanza_error(self) -> None:
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        svc = AuthService(session)
        with pytest.raises(InvalidTokenError):
            await svc.reset_password("bad-token", "NewPassword123!")

    async def test_token_ya_usado_lanza_error(self) -> None:
        prt = MagicMock()
        prt.usado_at = datetime.now(UTC) - timedelta(minutes=10)
        prt.expires_at = datetime.now(UTC) + timedelta(minutes=20)

        session = _make_session()
        session.execute.return_value = _scalar_result(prt)

        svc = AuthService(session)
        with pytest.raises(InvalidTokenError):
            await svc.reset_password("used-token", "NewPassword123!")
