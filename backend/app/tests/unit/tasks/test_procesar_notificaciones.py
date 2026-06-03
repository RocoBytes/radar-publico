"""Tests unitarios del canal WhatsApp en procesar_notificaciones.

Cubre:
- whatsapp_enabled=False → notif fallida con 'whatsapp_deshabilitado'.
- whatsapp_activo=False en preferencias → cancelada.
- whatsapp_pausado_hasta en el futuro → cancelada.
- whatsapp_solo_criticas + tipo no crítico → cancelada.
- empresa sin contacto_telefono → fallida.
- envío exitoso → notif enviada (sender mockeado).

No prueba email ni in_app — esos canales tienen cobertura suficiente en el
pipeline existente y no se modificaron.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete

# ---------------------------------------------------------------------------
# Fixtures de limpieza
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _limpieza() -> None:  # type: ignore[misc]
    from app.db.session import AsyncSessionLocal
    from app.models.notificacion import Notificacion

    async def _borrar() -> None:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Notificacion).where(Notificacion.titulo.like("TEST-WA%")))
            await session.commit()

    await _borrar()
    yield  # type: ignore[misc]
    await _borrar()


@pytest_asyncio.fixture
async def empresa_con_whatsapp() -> dict[str, object]:  # type: ignore[misc]
    """Empresa con teléfono + preferencias WhatsApp activas."""
    from app.db.session import AsyncSessionLocal
    from app.models.empresa import Empresa
    from app.models.enums import UserRole, UserStatus
    from app.models.preferencias import PreferenciasNotificaciones
    from app.models.usuario import Usuario

    email = f"test_wa_{uuid.uuid4().hex[:8]}@test.cl"
    rut = f"76.{uuid.uuid4().int % 999_999:06d}-K"

    async with AsyncSessionLocal() as session:
        usuario = Usuario(
            email=email,
            password_hash="$2b$12$placeholder",
            rol=UserRole.proveedor,
            status=UserStatus.active,
            must_change_password=False,
        )
        session.add(usuario)
        await session.flush()

        empresa = Empresa(
            usuario_id=usuario.id,
            rut=rut,
            razon_social="Empresa WA Test SpA",
            contacto_telefono="+56912345678",
        )
        session.add(empresa)
        await session.flush()

        prefs = PreferenciasNotificaciones(
            empresa_id=empresa.id,
            whatsapp_activo=True,
            whatsapp_solo_criticas=False,
        )
        session.add(prefs)
        await session.commit()

        ids = {
            "usuario_id": usuario.id,
            "empresa_id": empresa.id,
        }

    yield ids  # type: ignore[misc]

    from app.db.session import AsyncSessionLocal
    from app.models.usuario import Usuario

    async with AsyncSessionLocal() as session:
        u = await session.get(Usuario, ids["usuario_id"])
        if u is not None:
            await session.delete(u)
            await session.commit()


async def _crear_notif_whatsapp(
    empresa_id: object,
    *,
    tipo: str = "nueva_oportunidad",
) -> uuid.UUID:
    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifCanal, NotifStatus, NotifTipo
    from app.models.notificacion import Notificacion

    async with AsyncSessionLocal() as session:
        notif = Notificacion(
            empresa_id=empresa_id,
            tipo=NotifTipo(tipo),
            canal=NotifCanal.whatsapp,
            status=NotifStatus.pendiente,
            titulo="TEST-WA notificación",
            cuerpo="Cuerpo de prueba WhatsApp",
            datos={},
            programada_para=datetime.now(UTC) - timedelta(seconds=1),
        )
        session.add(notif)
        await session.commit()
        return notif.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_whatsapp_deshabilitado(
    empresa_con_whatsapp: dict[str, object],
) -> None:
    """Con WHATSAPP_ENABLED=False, la notif queda fallida sin llamar a Twilio."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifStatus
    from app.models.notificacion import Notificacion
    from app.tasks.procesar_notificaciones import _procesar_notificaciones

    empresa_id = empresa_con_whatsapp["empresa_id"]
    notif_id = await _crear_notif_whatsapp(empresa_id)

    with patch("app.config.settings.whatsapp_enabled", False):
        await _procesar_notificaciones()

    async with AsyncSessionLocal() as session:
        notif = await session.get(Notificacion, notif_id)
    assert notif is not None
    assert notif.status == NotifStatus.fallida
    assert "whatsapp_deshabilitado" in (notif.error_mensaje or "")


@pytest.mark.asyncio
async def test_whatsapp_inactivo_en_preferencias(
    empresa_con_whatsapp: dict[str, object],
) -> None:
    """whatsapp_activo=False en preferencias → notif cancelada."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifStatus
    from app.models.notificacion import Notificacion
    from app.models.preferencias import PreferenciasNotificaciones
    from app.tasks.procesar_notificaciones import _procesar_notificaciones

    empresa_id = empresa_con_whatsapp["empresa_id"]

    # Desactivar WhatsApp en preferencias
    async with AsyncSessionLocal() as session:
        prefs = await session.get(PreferenciasNotificaciones, empresa_id)
        assert prefs is not None
        prefs.whatsapp_activo = False
        await session.commit()

    notif_id = await _crear_notif_whatsapp(empresa_id)

    with patch("app.config.settings.whatsapp_enabled", True):
        await _procesar_notificaciones()

    async with AsyncSessionLocal() as session:
        notif = await session.get(Notificacion, notif_id)
    assert notif is not None
    assert notif.status == NotifStatus.cancelada
    assert "whatsapp_inactivo" in (notif.error_mensaje or "")


@pytest.mark.asyncio
async def test_whatsapp_pausado(
    empresa_con_whatsapp: dict[str, object],
) -> None:
    """whatsapp_pausado_hasta en el futuro → notif cancelada."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifStatus
    from app.models.notificacion import Notificacion
    from app.models.preferencias import PreferenciasNotificaciones
    from app.tasks.procesar_notificaciones import _procesar_notificaciones

    empresa_id = empresa_con_whatsapp["empresa_id"]
    futuro = datetime.now(UTC) + timedelta(days=7)

    async with AsyncSessionLocal() as session:
        prefs = await session.get(PreferenciasNotificaciones, empresa_id)
        assert prefs is not None
        prefs.whatsapp_pausado_hasta = futuro
        await session.commit()

    notif_id = await _crear_notif_whatsapp(empresa_id)

    with patch("app.config.settings.whatsapp_enabled", True):
        await _procesar_notificaciones()

    async with AsyncSessionLocal() as session:
        notif = await session.get(Notificacion, notif_id)
    assert notif is not None
    assert notif.status == NotifStatus.cancelada
    assert "whatsapp_pausado" in (notif.error_mensaje or "")


@pytest.mark.asyncio
async def test_whatsapp_solo_criticas_ignora_sistema(
    empresa_con_whatsapp: dict[str, object],
) -> None:
    """solo_criticas=True + tipo=sistema → notif cancelada."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifStatus
    from app.models.notificacion import Notificacion
    from app.models.preferencias import PreferenciasNotificaciones
    from app.tasks.procesar_notificaciones import _procesar_notificaciones

    empresa_id = empresa_con_whatsapp["empresa_id"]

    async with AsyncSessionLocal() as session:
        prefs = await session.get(PreferenciasNotificaciones, empresa_id)
        assert prefs is not None
        prefs.whatsapp_solo_criticas = True
        await session.commit()

    notif_id = await _crear_notif_whatsapp(empresa_id, tipo="sistema")

    with patch("app.config.settings.whatsapp_enabled", True):
        await _procesar_notificaciones()

    async with AsyncSessionLocal() as session:
        notif = await session.get(Notificacion, notif_id)
    assert notif is not None
    assert notif.status == NotifStatus.cancelada
    assert "whatsapp_solo_criticas" in (notif.error_mensaje or "")


@pytest.mark.asyncio
async def test_whatsapp_sin_telefono(
    empresa_con_whatsapp: dict[str, object],
) -> None:
    """Empresa sin contacto_telefono → notif fallida."""
    from app.db.session import AsyncSessionLocal
    from app.models.empresa import Empresa
    from app.models.enums import NotifStatus
    from app.models.notificacion import Notificacion
    from app.tasks.procesar_notificaciones import _procesar_notificaciones

    empresa_id = empresa_con_whatsapp["empresa_id"]

    async with AsyncSessionLocal() as session:
        emp = await session.get(Empresa, empresa_id)
        assert emp is not None
        emp.contacto_telefono = None
        await session.commit()

    notif_id = await _crear_notif_whatsapp(empresa_id)

    with patch("app.config.settings.whatsapp_enabled", True):
        await _procesar_notificaciones()

    async with AsyncSessionLocal() as session:
        notif = await session.get(Notificacion, notif_id)
    assert notif is not None
    assert notif.status == NotifStatus.fallida
    assert "whatsapp_sin_telefono" in (notif.error_mensaje or "")


@pytest.mark.asyncio
async def test_whatsapp_envio_exitoso(
    empresa_con_whatsapp: dict[str, object],
) -> None:
    """Todos los checks pasan + sender mockeado → notif enviada."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifStatus
    from app.models.notificacion import Notificacion
    from app.tasks.procesar_notificaciones import _procesar_notificaciones

    empresa_id = empresa_con_whatsapp["empresa_id"]
    notif_id = await _crear_notif_whatsapp(empresa_id)

    mock_sender = AsyncMock(return_value="SM_TEST_SID")

    with (
        patch("app.config.settings.whatsapp_enabled", True),
        patch("app.services.whatsapp.sender.send_whatsapp", mock_sender),
    ):
        await _procesar_notificaciones()

    mock_sender.assert_awaited_once()
    call_kwargs = mock_sender.call_args
    assert call_kwargs.kwargs.get("to_number") == "+56912345678"

    async with AsyncSessionLocal() as session:
        notif = await session.get(Notificacion, notif_id)
    assert notif is not None
    assert notif.status == NotifStatus.enviada
    assert notif.enviada_at is not None
