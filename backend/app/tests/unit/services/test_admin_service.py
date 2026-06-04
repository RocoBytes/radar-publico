"""Tests unitarios de AdminService con mocks de AsyncSession.

Se verifica lógica de negocio sin tocar la base de datos real.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from app.models.enums import TicketStatus, UserRole, UserStatus
from app.services.admin.exceptions import (
    CuentaNoEncontradaError,
    CuentaYaExisteError,
    EmpresaNoEncontradaError,
)
from app.services.admin.service import AdminService

# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------

_EMAIL_PATCH = "app.services.admin.service.email_sender.send_email"
_LOG_PATCH = "app.services.admin.service.log_event"
_ENC_PATCH = "app.core.encryption.settings"


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _scalar_result(value: Any) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    result.scalars.return_value.all.return_value = []
    return result


def _make_usuario(**kwargs: Any) -> MagicMock:
    u = MagicMock()
    u.id = kwargs.get("id", uuid.uuid4())
    u.email = kwargs.get("email", "proveedor@example.cl")
    u.rol = kwargs.get("rol", UserRole.proveedor)
    u.status = kwargs.get("status", UserStatus.active)
    u.must_change_password = kwargs.get("must_change_password", True)
    u.deleted_at = None
    u.empresa = kwargs.get("empresa")
    u.created_at = kwargs.get("created_at")
    return u


def _make_empresa(**kwargs: Any) -> MagicMock:
    e = MagicMock()
    e.id = kwargs.get("id", uuid.uuid4())
    e.rut = kwargs.get("rut", "76.123.456-7")
    e.razon_social = kwargs.get("razon_social", "Test SpA")
    e.ticket = kwargs.get("ticket")
    return e


def _make_ticket(**kwargs: Any) -> MagicMock:
    t = MagicMock()
    t.id = kwargs.get("id", uuid.uuid4())
    t.ticket_ultimos_4 = kwargs.get("ticket_ultimos_4", "1234")
    t.ticket_cifrado = kwargs.get("ticket_cifrado", "cifrado_base64")
    t.status = kwargs.get("status", TicketStatus.active)
    t.cargado_at = kwargs.get("cargado_at")
    return t


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCrearCuenta:
    async def test_crear_cuenta_ok(self) -> None:
        """Happy path: crea usuario + empresa, retorna contraseña temporal."""
        session = _make_session()
        mock_usuario_reload = _make_usuario(email="nuevo@example.cl")
        session.execute.side_effect = [
            _scalar_result(None),                    # email no existe
            _scalar_result(None),                    # rut no existe
            _scalar_result(mock_usuario_reload),     # reload usuario tras commit
        ]

        with (
            patch(_EMAIL_PATCH, new_callable=AsyncMock),
            patch(_LOG_PATCH, new_callable=AsyncMock),
            patch(_ENC_PATCH) as mock_enc_settings,
        ):
            mock_enc_settings.encryption_key = "A" * 32
            svc = AdminService(session)
            usuario, temp_password = await svc.crear_cuenta(
                email="nuevo@example.cl",
                rut="76.123.456-7",
                razon_social="Empresa Nueva SpA",
                creado_por_id=uuid.uuid4(),
            )

        # add llamado dos veces: usuario + empresa
        assert session.add.call_count == 2
        session.commit.assert_called_once()
        assert isinstance(temp_password, str)
        assert len(temp_password) > 0

    async def test_crear_cuenta_email_duplicado(self) -> None:
        """Lanza CuentaYaExisteError(campo='email') si el email ya existe."""
        session = _make_session()
        session.execute.return_value = _scalar_result(_make_usuario())

        svc = AdminService(session)
        with pytest.raises(CuentaYaExisteError) as exc_info:
            await svc.crear_cuenta(
                email="existente@example.cl",
                rut="76.999.888-K",
                razon_social="Otra Empresa SpA",
                creado_por_id=uuid.uuid4(),
            )

        assert exc_info.value.campo == "email"
        session.commit.assert_not_called()

    async def test_crear_cuenta_rut_duplicado(self) -> None:
        """Lanza CuentaYaExisteError(campo='rut') si el RUT ya existe."""
        session = _make_session()
        session.execute.side_effect = [
            _scalar_result(None),  # email no existe
            _scalar_result(_make_empresa()),  # rut ya existe
        ]

        svc = AdminService(session)
        with pytest.raises(CuentaYaExisteError) as exc_info:
            await svc.crear_cuenta(
                email="nuevo@example.cl",
                rut="76.123.456-7",
                razon_social="Empresa Duplicada SpA",
                creado_por_id=uuid.uuid4(),
            )

        assert exc_info.value.campo == "rut"
        session.commit.assert_not_called()


@pytest.mark.asyncio
class TestCambiarEstado:
    async def test_cambiar_estado_suspender(self) -> None:
        """Accion 'suspender' setea status=suspended."""
        usuario = _make_usuario(status=UserStatus.active)
        session = _make_session()
        session.execute.return_value = _scalar_result(usuario)

        with patch(_LOG_PATCH, new_callable=AsyncMock):
            svc = AdminService(session)
            await svc.cambiar_estado(
                usuario_id=usuario.id,
                accion="suspender",
                admin_id=uuid.uuid4(),
            )

        assert usuario.status == UserStatus.suspended
        session.commit.assert_called_once()

    async def test_cambiar_estado_reactivar(self) -> None:
        """Accion 'reactivar' setea status=active."""
        usuario = _make_usuario(status=UserStatus.suspended)
        session = _make_session()
        session.execute.return_value = _scalar_result(usuario)

        with patch(_LOG_PATCH, new_callable=AsyncMock):
            svc = AdminService(session)
            await svc.cambiar_estado(
                usuario_id=usuario.id,
                accion="reactivar",
                admin_id=uuid.uuid4(),
            )

        assert usuario.status == UserStatus.active
        session.commit.assert_called_once()

    async def test_cambiar_estado_usuario_no_existe(self) -> None:
        """Lanza CuentaNoEncontradaError si el usuario no existe."""
        session = _make_session()
        session.execute.return_value = _scalar_result(None)

        svc = AdminService(session)
        with pytest.raises(CuentaNoEncontradaError):
            await svc.cambiar_estado(
                usuario_id=uuid.uuid4(),
                accion="suspender",
                admin_id=uuid.uuid4(),
            )


@pytest.mark.asyncio
class TestCargarTicket:
    async def test_cargar_ticket_nuevo(self) -> None:
        """Crea TicketApi nuevo cuando la empresa no tenía ticket.

        Verifica ultimos_4 y que ticket_cifrado != plaintext.
        """
        empresa = _make_empresa(ticket=None)
        usuario = _make_usuario(empresa=empresa)
        session = _make_session()
        session.execute.return_value = _scalar_result(usuario)

        ticket_plaintext = "TOKEN_LARGO_12345678901234567890"

        with (
            patch(_LOG_PATCH, new_callable=AsyncMock),
            patch(_ENC_PATCH) as mock_enc_settings,
        ):
            mock_enc_settings.encryption_key = "A" * 32
            svc = AdminService(session)
            await svc.cargar_ticket(
                usuario_id=usuario.id,
                ticket_plaintext=ticket_plaintext,
                admin_id=uuid.uuid4(),
            )

        session.add.assert_called_once()
        session.commit.assert_called_once()
        added_ticket = session.add.call_args[0][0]
        assert added_ticket.ticket_ultimos_4 == ticket_plaintext[-4:]
        assert added_ticket.ticket_cifrado != ticket_plaintext
        assert added_ticket.status == TicketStatus.active

    async def test_cargar_ticket_update(self) -> None:
        """Segunda carga actualiza el ticket existente sin duplicar."""
        ticket_existente = _make_ticket(ticket_ultimos_4="0000")
        empresa = _make_empresa(ticket=ticket_existente)
        usuario = _make_usuario(empresa=empresa)
        session = _make_session()
        session.execute.return_value = _scalar_result(usuario)

        nuevo_ticket_plaintext = "NUEVO_TOKEN_LARGO_9999999999"

        with (
            patch(_LOG_PATCH, new_callable=AsyncMock),
            patch(_ENC_PATCH) as mock_enc_settings,
        ):
            mock_enc_settings.encryption_key = "A" * 32
            svc = AdminService(session)
            await svc.cargar_ticket(
                usuario_id=usuario.id,
                ticket_plaintext=nuevo_ticket_plaintext,
                admin_id=uuid.uuid4(),
            )

        # No se creó un ticket nuevo — se actualizó el existente in-place
        session.add.assert_not_called()
        session.commit.assert_called_once()
        assert ticket_existente.ticket_ultimos_4 == nuevo_ticket_plaintext[-4:]
        assert ticket_existente.ticket_cifrado != nuevo_ticket_plaintext
        assert ticket_existente.status == TicketStatus.active

    async def test_cargar_ticket_usuario_sin_empresa(self) -> None:
        """Lanza EmpresaNoEncontradaError si el usuario no tiene empresa."""
        usuario = _make_usuario(empresa=None)
        session = _make_session()
        session.execute.return_value = _scalar_result(usuario)

        with patch(_ENC_PATCH) as mock_enc_settings:
            mock_enc_settings.encryption_key = "A" * 32
            svc = AdminService(session)
            with pytest.raises(EmpresaNoEncontradaError):
                await svc.cargar_ticket(
                    usuario_id=usuario.id,
                    ticket_plaintext="CUALQUIER_TOKEN_LARGO",
                    admin_id=uuid.uuid4(),
                )
