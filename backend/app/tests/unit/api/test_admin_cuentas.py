"""Tests para los nuevos endpoints de admin: impersonar y diagnosticar ticket.

Cubre:
- POST /api/admin/cuentas/{id}/impersonar → token JWT de 1h con claim extra
- GET /api/admin/cuentas/{id}/ticket/diagnostico → info sin ticket y con ticket
- Autenticación: 401 sin token, 403 si no es admin
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.security import create_access_token, decode_access_token
from app.models.enums import TicketStatus, UserRole, UserStatus

if TYPE_CHECKING:
    from collections.abc import Callable
    from sqlalchemy.ext.asyncio import AsyncSession


def _headers(user_id: str) -> dict[str, str]:
    token = create_access_token(subject=user_id)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Tests de impersonación
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_impersonar_retorna_token(
    client: AsyncClient,
    make_user: Callable[..., Any],
) -> None:
    """El admin obtiene un JWT de impersonación con claim extra."""
    admin = await make_user(
        email="admin_imp@test.cl",
        rol=UserRole.admin,
        with_empresa=False,
    )
    proveedor = await make_user(email="prov_imp@test.cl")

    resp = await client.post(
        f"/api/admin/cuentas/{proveedor.id}/impersonar",
        headers=_headers(str(admin.id)),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 3600

    payload = decode_access_token(data["access_token"])
    assert payload.sub == str(proveedor.id)

    from jose import jwt as _jwt
    from app.config import settings

    raw = _jwt.decode(data["access_token"], settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert raw.get("impersonated_by_admin_id") == str(admin.id)


@pytest.mark.asyncio
async def test_impersonar_usuario_inexistente(
    client: AsyncClient,
    make_user: Callable[..., Any],
) -> None:
    """Impersonar un ID desconocido retorna 404."""
    import uuid

    admin = await make_user(
        email="admin_imp2@test.cl",
        rol=UserRole.admin,
        with_empresa=False,
    )
    resp = await client.post(
        f"/api/admin/cuentas/{uuid.uuid4()}/impersonar",
        headers=_headers(str(admin.id)),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_impersonar_requiere_admin(
    client: AsyncClient,
    make_user: Callable[..., Any],
) -> None:
    """Un proveedor no puede usar el endpoint de impersonación."""
    proveedor1 = await make_user(email="prov_imp_a@test.cl")
    proveedor2 = await make_user(email="prov_imp_b@test.cl")

    resp = await client.post(
        f"/api/admin/cuentas/{proveedor2.id}/impersonar",
        headers=_headers(str(proveedor1.id)),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tests de diagnóstico de ticket
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_diagnostico_sin_ticket(
    client: AsyncClient,
    make_user: Callable[..., Any],
) -> None:
    """Empresa sin ticket → tiene_ticket=False, llamadas_hoy=0."""
    admin = await make_user(
        email="admin_diag@test.cl",
        rol=UserRole.admin,
        with_empresa=False,
    )
    proveedor = await make_user(email="prov_diag@test.cl")

    resp = await client.get(
        f"/api/admin/cuentas/{proveedor.id}/ticket/diagnostico",
        headers=_headers(str(admin.id)),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tiene_ticket"] is False
    assert data["llamadas_hoy"] == 0
    assert data["test_ok"] is None


@pytest.mark.asyncio
async def test_diagnostico_con_ticket(
    client: AsyncClient,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """Empresa con ticket activo → tiene_ticket=True con últimos 4."""
    from app.core.encryption import encrypt_ticket
    from app.models.empresa import Empresa
    from app.models.ticket import TicketApi

    admin = await make_user(
        email="admin_diag2@test.cl",
        rol=UserRole.admin,
        with_empresa=False,
    )
    proveedor = await make_user(email="prov_diag2@test.cl")

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await db_session.execute(
        select(Empresa).where(Empresa.usuario_id == proveedor.id)
    )
    empresa = result.scalar_one()

    ticket = TicketApi(
        empresa_id=empresa.id,
        ticket_cifrado=encrypt_ticket("TOKEN-FAKE-1234"),
        ticket_ultimos_4="1234",
        status=TicketStatus.active,
        cargado_por_admin_id=None,  # sin FK para evitar restricción en teardown
        cargado_at=datetime.now(UTC),
    )
    db_session.add(ticket)
    await db_session.commit()

    try:
        resp = await client.get(
            f"/api/admin/cuentas/{proveedor.id}/ticket/diagnostico",
            headers=_headers(str(admin.id)),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tiene_ticket"] is True
        assert data["ticket_ultimos_4"] == "1234"
        assert data["ticket_status"] == "active"
        assert data["llamadas_hoy"] == 0
        assert data["test_ok"] is None
    finally:
        await db_session.delete(ticket)
        await db_session.commit()


@pytest.mark.asyncio
async def test_diagnostico_test_conexion_mockeado(
    client: AsyncClient,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """test_conexion=True llama al cliente de ChileCompra (mockeado)."""
    from app.core.encryption import encrypt_ticket
    from app.models.empresa import Empresa
    from app.models.ticket import TicketApi
    from sqlalchemy import select

    admin = await make_user(
        email="admin_diag3@test.cl",
        rol=UserRole.admin,
        with_empresa=False,
    )
    proveedor = await make_user(email="prov_diag3@test.cl")

    result = await db_session.execute(
        select(Empresa).where(Empresa.usuario_id == proveedor.id)
    )
    empresa = result.scalar_one()

    ticket = TicketApi(
        empresa_id=empresa.id,
        ticket_cifrado=encrypt_ticket("TOKEN-FAKE-5678"),
        ticket_ultimos_4="5678",
        status=TicketStatus.active,
        cargado_por_admin_id=None,  # sin FK al admin para evitar restricción en teardown
        cargado_at=datetime.now(UTC),
    )
    db_session.add(ticket)
    await db_session.commit()

    mock_lista = AsyncMock(return_value=None)

    try:
        # El target correcto: donde la clase vive, no donde se importa lazy
        with patch(
            "app.services.chilecompra.client.MercadoPublicoClient",
        ) as MockClient:
            mock_instance = AsyncMock()
            mock_instance.listar_licitaciones_por_estado = AsyncMock(return_value=None)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = await client.get(
                f"/api/admin/cuentas/{proveedor.id}/ticket/diagnostico?test_conexion=true",
                headers=_headers(str(admin.id)),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["test_ok"] is True
        assert data["test_duracion_ms"] is not None
    finally:
        await db_session.delete(ticket)
        await db_session.commit()


@pytest.mark.asyncio
async def test_diagnostico_usuario_inexistente(
    client: AsyncClient,
    make_user: Callable[..., Any],
) -> None:
    """ID desconocido retorna 404."""
    import uuid

    admin = await make_user(
        email="admin_diag4@test.cl",
        rol=UserRole.admin,
        with_empresa=False,
    )
    resp = await client.get(
        f"/api/admin/cuentas/{uuid.uuid4()}/ticket/diagnostico",
        headers=_headers(str(admin.id)),
    )
    assert resp.status_code == 404
