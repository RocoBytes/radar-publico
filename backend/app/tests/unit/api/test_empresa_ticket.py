"""Tests unitarios para GET /api/v1/empresa/ticket-status.

Cubre:
- Empresa sin ticket → 200, tiene_ticket=False, resto null/0.
- Empresa con ticket activo → 200, campos correctos.
- Conteo de requests_hoy via ApiQuotaLog.
- Sin token → 401.
- Usuario sin empresa asociada → 404.

Usa BD de test real (NullPool via conftest) con AsyncClient + ASGITransport.
Los tokens JWT se generan directamente desde app.core.security.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.core.security import create_access_token
from app.models.api_log import ApiQuotaLog
from app.models.empresa import Empresa
from app.models.enums import TicketStatus, UserRole, UserStatus
from app.models.ticket import TicketApi

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_headers(user_id: str) -> dict[str, str]:
    """Genera cabecera Authorization con JWT válido para el user_id dado."""
    token = create_access_token(subject=user_id)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _limpiar_tickets(db_session: AsyncSession) -> None:  # type: ignore[misc]
    """Elimina tickets y logs de quota antes y después de cada test para aislar el estado."""

    async def _borrar() -> None:
        # Primero los logs (FK a tickets_api)
        await db_session.execute(delete(ApiQuotaLog))
        await db_session.execute(delete(TicketApi))
        await db_session.commit()

    await _borrar()
    yield  # type: ignore[misc]
    await _borrar()


@pytest_asyncio.fixture
async def empresa_con_usuario(
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> tuple[Any, Empresa]:
    """Crea un usuario proveedor activo con empresa asociada.

    Retorna (usuario, empresa).
    """
    user: Any = await make_user(
        email="ticket_test@example.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        rut="76.555.444-3",
        razon_social="Ticket Test SpA",
    )
    result = await db_session.execute(select(Empresa).where(Empresa.usuario_id == user.id))
    empresa: Empresa = result.scalar_one()
    return user, empresa


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ticket_status_sin_ticket(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Empresa],
) -> None:
    """Empresa sin ticket → 200, tiene_ticket=False, el resto null o 0."""
    user, _ = empresa_con_usuario

    r = await client.get(
        "/api/v1/empresa/ticket-status",
        headers=_auth_headers(str(user.id)),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["tiene_ticket"] is False
    assert data["status"] is None
    assert data["ticket_ultimos_4"] is None
    assert data["cargado_at"] is None
    assert data["ultima_validacion_at"] is None
    assert data["ultimo_error"] is None
    assert data["cuota_diaria_max"] is None
    assert data["requests_hoy"] == 0


@pytest.mark.asyncio
async def test_ticket_status_con_ticket(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Empresa],
    db_session: AsyncSession,
) -> None:
    """Empresa con ticket activo → 200, tiene_ticket=True, campos correctos."""
    user, empresa = empresa_con_usuario

    ticket = TicketApi(
        empresa_id=empresa.id,
        ticket_cifrado="dummy-cifrado-para-test",
        ticket_ultimos_4="1234",
        status=TicketStatus.active,
        cuota_diaria_max=10000,
    )
    db_session.add(ticket)
    await db_session.commit()

    r = await client.get(
        "/api/v1/empresa/ticket-status",
        headers=_auth_headers(str(user.id)),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["tiene_ticket"] is True
    assert data["status"] == "active"
    assert data["ticket_ultimos_4"] == "1234"
    assert data["cuota_diaria_max"] == 10000


@pytest.mark.asyncio
async def test_ticket_status_requests_hoy(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Empresa],
    db_session: AsyncSession,
) -> None:
    """Ticket + 3 ApiQuotaLog con created_at=now() → requests_hoy=3."""
    user, empresa = empresa_con_usuario

    ticket = TicketApi(
        empresa_id=empresa.id,
        ticket_cifrado="dummy-cifrado-para-test",
        ticket_ultimos_4="5678",
        status=TicketStatus.active,
        cuota_diaria_max=10000,
    )
    db_session.add(ticket)
    await db_session.flush()

    ahora = datetime.now(UTC)
    for i in range(3):
        db_session.add(
            ApiQuotaLog(
                ticket_id=ticket.id,
                empresa_id=empresa.id,
                endpoint=f"/licitaciones?fecha={i}",
                metodo="GET",
                status_code=200,
                created_at=ahora,
            )
        )
    await db_session.commit()

    r = await client.get(
        "/api/v1/empresa/ticket-status",
        headers=_auth_headers(str(user.id)),
    )
    assert r.status_code == 200
    assert r.json()["requests_hoy"] == 3


@pytest.mark.asyncio
async def test_ticket_status_requiere_auth(client: AsyncClient) -> None:
    """GET /empresa/ticket-status sin token → 401."""
    r = await client.get("/api/v1/empresa/ticket-status")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_ticket_status_404_sin_empresa(
    client: AsyncClient,
    make_user: Callable[..., Any],
) -> None:
    """Usuario sin empresa asociada → 404."""
    # make_user sin with_empresa=True crea un usuario huérfano (sin empresa)
    user: Any = await make_user(
        email="sin_empresa_ticket@example.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
    )

    r = await client.get(
        "/api/v1/empresa/ticket-status",
        headers=_auth_headers(str(user.id)),
    )
    assert r.status_code == 404
