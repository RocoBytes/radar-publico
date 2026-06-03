"""Tests de integración para los flujos completos del Sprint 6.

Cruzan módulos reales (admin → proveedor API, notificaciones → procesador).
Usan BD de test (NullPool — conftest patch_db_session) y cliente ASGI.

Flujos cubiertos:
- Token de impersonación autentica en la API del proveedor
- POST impersonar graba EventoAuditoria con acción correcta
- Diagnóstico de ticket cuenta ApiQuotaLog del día correctamente
- in_app pendiente → enviada tras _procesar_notificaciones
- Notif ya enviada no se reprocesa (idempotencia)
- Email + in_app en paralelo: ambos quedan enviados
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.core.security import create_access_token
from app.models.enums import UserRole

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


def _headers(user_id: str) -> dict[str, str]:
    token = create_access_token(subject=user_id)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Limpieza de notificaciones de prueba
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _limpieza_notifs() -> None:  # type: ignore[misc]
    from app.db.session import AsyncSessionLocal
    from app.models.notificacion import Notificacion

    async def _borrar() -> None:
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(Notificacion).where(Notificacion.titulo.like("E2E-SPRINT6%"))
            )
            await session.commit()

    await _borrar()
    yield  # type: ignore[misc]
    await _borrar()


# ---------------------------------------------------------------------------
# Fixture de empresa para tests de notificaciones
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def empresa_test() -> dict[str, Any]:  # type: ignore[misc]
    """Usuario + Empresa mínimos para tests de notificaciones E2E."""
    from app.db.session import AsyncSessionLocal
    from app.models.empresa import Empresa
    from app.models.enums import UserStatus
    from app.models.usuario import Usuario

    suffix = uuid.uuid4().hex[:8]
    email = f"e2e_notif_{suffix}@test.cl"
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
            razon_social="Empresa E2E SpA",
        )
        session.add(empresa)
        await session.commit()

        ids: dict[str, Any] = {
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


# ---------------------------------------------------------------------------
# Helper para crear notificaciones de prueba
# ---------------------------------------------------------------------------


async def _crear_notif(
    empresa_id: Any,
    *,
    canal: str = "in_app",
    status: str = "pendiente",
    titulo: str = "E2E-SPRINT6 notif",
) -> uuid.UUID:
    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifCanal, NotifStatus, NotifTipo
    from app.models.notificacion import Notificacion

    async with AsyncSessionLocal() as session:
        notif = Notificacion(
            empresa_id=empresa_id,
            tipo=NotifTipo.nueva_oportunidad,
            canal=NotifCanal(canal),
            status=NotifStatus(status),
            titulo=titulo,
            cuerpo="Cuerpo de prueba E2E",
            datos={},
            programada_para=datetime.now(UTC) - timedelta(seconds=1),
        )
        session.add(notif)
        await session.commit()
        return notif.id


# ---------------------------------------------------------------------------
# Impersonación: token autentica en la API del proveedor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_impersonar_token_autentica_api_proveedor(
    client: AsyncClient,
    make_user: Callable[..., Any],
) -> None:
    """El JWT de impersonación permite acceder a endpoints del proveedor."""
    admin = await make_user(
        email="e2e_imp_admin@test.cl",
        rol=UserRole.admin,
        with_empresa=False,
    )
    proveedor = await make_user(email="e2e_imp_prov@test.cl")

    resp = await client.post(
        f"/api/admin/cuentas/{proveedor.id}/impersonar",
        headers=_headers(str(admin.id)),
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    resp2 = await client.get(
        "/api/v1/notificaciones/resumen",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# Impersonación: evento de auditoría
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_impersonar_crea_evento_auditoria(
    client: AsyncClient,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """POST /impersonar escribe EventoAuditoria con accion y recurso_id correctos."""
    from app.models.eventos_auditoria import EventoAuditoria

    admin = await make_user(
        email="e2e_audit_admin@test.cl",
        rol=UserRole.admin,
        with_empresa=False,
    )
    proveedor = await make_user(email="e2e_audit_prov@test.cl")

    resp = await client.post(
        f"/api/admin/cuentas/{proveedor.id}/impersonar",
        headers=_headers(str(admin.id)),
    )
    assert resp.status_code == 200

    result = await db_session.execute(
        select(EventoAuditoria)
        .where(
            EventoAuditoria.accion == "admin.cuenta.impersonada",
            EventoAuditoria.usuario_id == admin.id,
        )
        .order_by(EventoAuditoria.created_at.desc())
        .limit(1)
    )
    evento = result.scalar_one_or_none()
    assert evento is not None
    assert evento.recurso_id == str(proveedor.id)


# ---------------------------------------------------------------------------
# Diagnóstico: llamadas_hoy cuenta registros del día para el ticket
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_diagnostico_llamadas_hoy_cuenta_registros(
    client: AsyncClient,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """llamadas_hoy == N cuando hay N ApiQuotaLog de hoy para ese ticket."""
    from app.core.encryption import encrypt_ticket
    from app.models.api_log import ApiQuotaLog
    from app.models.empresa import Empresa
    from app.models.enums import TicketStatus
    from app.models.ticket import TicketApi

    admin = await make_user(
        email="e2e_quota_admin@test.cl",
        rol=UserRole.admin,
        with_empresa=False,
    )
    proveedor = await make_user(email="e2e_quota_prov@test.cl")

    result = await db_session.execute(select(Empresa).where(Empresa.usuario_id == proveedor.id))
    empresa = result.scalar_one()

    ticket = TicketApi(
        empresa_id=empresa.id,
        ticket_cifrado=encrypt_ticket("TOKEN-E2E-9999"),
        ticket_ultimos_4="9999",
        status=TicketStatus.active,
        cargado_por_admin_id=None,
        cargado_at=datetime.now(UTC),
    )
    db_session.add(ticket)
    await db_session.commit()

    llamadas = 5
    logs = [
        ApiQuotaLog(
            ticket_id=ticket.id,
            empresa_id=empresa.id,
            endpoint="/api/licitaciones",
            metodo="GET",
            status_code=200,
        )
        for _ in range(llamadas)
    ]
    db_session.add_all(logs)
    await db_session.commit()

    try:
        resp = await client.get(
            f"/api/admin/cuentas/{proveedor.id}/ticket/diagnostico",
            headers=_headers(str(admin.id)),
        )
        assert resp.status_code == 200
        assert resp.json()["llamadas_hoy"] == llamadas
    finally:
        for log in logs:
            await db_session.delete(log)
        await db_session.delete(ticket)
        await db_session.commit()


# ---------------------------------------------------------------------------
# Procesamiento de notificaciones: in_app
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_procesar_notif_in_app_marca_enviada(
    empresa_test: dict[str, Any],
) -> None:
    """Notif in_app pendiente queda enviada tras _procesar_notificaciones."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifStatus
    from app.models.notificacion import Notificacion
    from app.tasks.procesar_notificaciones import _procesar_notificaciones

    notif_id = await _crear_notif(
        empresa_test["empresa_id"],
        canal="in_app",
        titulo="E2E-SPRINT6 in_app",
    )

    stats = await _procesar_notificaciones()
    assert stats["enviadas"] >= 1

    async with AsyncSessionLocal() as session:
        notif = await session.get(Notificacion, notif_id)
    assert notif is not None
    assert notif.status == NotifStatus.enviada
    assert notif.enviada_at is not None


# ---------------------------------------------------------------------------
# Procesamiento de notificaciones: idempotencia
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_procesar_notif_idempotente(
    empresa_test: dict[str, Any],
) -> None:
    """Notif ya enviada no cambia al volver a procesar."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifStatus
    from app.models.notificacion import Notificacion
    from app.tasks.procesar_notificaciones import _procesar_notificaciones

    notif_id = await _crear_notif(
        empresa_test["empresa_id"],
        canal="in_app",
        status="enviada",
        titulo="E2E-SPRINT6 idempotente",
    )

    enviada_at_original = datetime.now(UTC) - timedelta(minutes=10)
    async with AsyncSessionLocal() as session:
        notif = await session.get(Notificacion, notif_id)
        assert notif is not None
        notif.enviada_at = enviada_at_original
        await session.commit()

    await _procesar_notificaciones()

    async with AsyncSessionLocal() as session:
        notif = await session.get(Notificacion, notif_id)
    assert notif is not None
    assert notif.status == NotifStatus.enviada
    # enviada_at no debe cambiar — la tarea no reprocesó la notif
    assert notif.enviada_at is not None
    delta = abs((notif.enviada_at - enviada_at_original).total_seconds())
    assert delta < 2


# ---------------------------------------------------------------------------
# Procesamiento de notificaciones: email mockeado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_procesar_notif_email_con_sender_mockeado(
    empresa_test: dict[str, Any],
) -> None:
    """Notif email pendiente queda enviada cuando send_email es mockeado."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifStatus
    from app.models.notificacion import Notificacion
    from app.tasks.procesar_notificaciones import _procesar_notificaciones

    notif_id = await _crear_notif(
        empresa_test["empresa_id"],
        canal="email",
        titulo="E2E-SPRINT6 email",
    )

    mock_send = AsyncMock(return_value=None)
    with patch("app.services.email.sender.send_email", mock_send):
        stats = await _procesar_notificaciones()

    assert stats["enviadas"] >= 1
    mock_send.assert_awaited_once()

    async with AsyncSessionLocal() as session:
        notif = await session.get(Notificacion, notif_id)
    assert notif is not None
    assert notif.status == NotifStatus.enviada


# ---------------------------------------------------------------------------
# Procesamiento de notificaciones: in_app + email simultáneos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_procesar_notif_multicanal_in_app_y_email(
    empresa_test: dict[str, Any],
) -> None:
    """in_app y email en el mismo batch: ambos quedan enviados."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifStatus
    from app.models.notificacion import Notificacion
    from app.tasks.procesar_notificaciones import _procesar_notificaciones

    empresa_id = empresa_test["empresa_id"]
    id_in_app = await _crear_notif(empresa_id, canal="in_app", titulo="E2E-SPRINT6 multi-in_app")
    id_email = await _crear_notif(empresa_id, canal="email", titulo="E2E-SPRINT6 multi-email")

    mock_send = AsyncMock(return_value=None)
    with patch("app.services.email.sender.send_email", mock_send):
        stats = await _procesar_notificaciones()

    assert stats["total"] >= 2
    assert stats["enviadas"] >= 2

    async with AsyncSessionLocal() as session:
        in_app = await session.get(Notificacion, id_in_app)
        email = await session.get(Notificacion, id_email)

    assert in_app is not None and in_app.status == NotifStatus.enviada
    assert email is not None and email.status == NotifStatus.enviada
