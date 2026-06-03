"""Fixtures compartidas para la suite E2E.

Complementa el conftest.py raíz (que provee: client, db_session,
make_user, patch_db_session, reset_redis_rate_limits).

Convenciones:
  - _auth_headers(user_id): genera Bearer token directo sin round-trip HTTP.
  - make_licitacion: crea + limpia Licitacion mínima con código único.
  - make_organismo: crea + limpia Organismo mínimo.
  - make_admin: crea usuario con rol admin.
  - make_ticket: asocia TicketApi cifrado a una empresa.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime
from typing import Any

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_ticket
from app.core.security import create_access_token
from app.models.empresa import Empresa
from app.models.enums import (
    LicitacionEstado,
    TicketStatus,
    UserRole,
    UserStatus,
)
from app.models.licitacion import Licitacion
from app.models.organismo import Organismo
from app.models.ticket import TicketApi
from app.models.usuario import Usuario


# ---------------------------------------------------------------------------
# Helper de autenticación (sin round-trip HTTP)
# ---------------------------------------------------------------------------


def auth_headers(user_id: str | uuid.UUID) -> dict[str, str]:
    token = create_access_token(subject=str(user_id))
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixture: admin user
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_admin(make_user: Callable[..., Any]) -> Callable[..., Any]:
    """Devuelve factory de usuarios admin."""

    async def _factory(email: str = "admin@radar.cl") -> Usuario:
        return await make_user(
            email=email,
            rol=UserRole.admin,
            status=UserStatus.active,
            must_change_password=False,
            with_empresa=False,
        )

    return _factory


# ---------------------------------------------------------------------------
# Fixture: organismo
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_organismo(
    db_session: AsyncSession,
) -> AsyncGenerator[Callable[..., Any], None]:
    codigos_creados: list[int] = []

    async def _factory(
        nombre: str = "Organismo de Prueba",
        codigo: int | None = None,
    ) -> Organismo:
        cod = codigo or (90000 + len(codigos_creados))
        existing = await db_session.get(Organismo, cod)
        if existing:
            return existing
        org = Organismo(
            codigo_organismo=cod,
            nombre=nombre,
        )
        db_session.add(org)
        await db_session.commit()
        await db_session.refresh(org)
        codigos_creados.append(cod)
        return org

    yield _factory

    for cod in codigos_creados:
        org = await db_session.get(Organismo, cod)
        if org is not None:
            await db_session.delete(org)
    await db_session.commit()


# ---------------------------------------------------------------------------
# Fixture: licitacion
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_licitacion(
    db_session: AsyncSession,
    make_organismo: Callable[..., Any],
) -> AsyncGenerator[Callable[..., Any], None]:
    codigos_creados: list[str] = []

    async def _factory(
        codigo: str | None = None,
        estado: LicitacionEstado = LicitacionEstado.publicada,
        nombre: str = "Licitación de prueba E2E",
        monto_estimado: float | None = 5_000_000.0,
        es_renovable: bool = False,
        duracion_meses: int | None = None,
        with_organismo: bool = True,
    ) -> Licitacion:
        cod = codigo or f"E2E-{uuid.uuid4().hex[:8].upper()}-L1"

        organismo = None
        if with_organismo:
            organismo = await make_organismo()

        lic = Licitacion(
            codigo=cod,
            nombre=nombre,
            estado=estado,
            moneda="CLP",
            es_renovable=es_renovable,
            duracion_estimada_meses=duracion_meses,  # campo real del modelo
            monto_estimado=monto_estimado,
            fecha_publicacion=datetime(2026, 1, 1, tzinfo=UTC),
            fecha_cierre=datetime(2026, 12, 31, tzinfo=UTC),
            codigo_organismo=organismo.codigo_organismo if organismo else None,
        )
        db_session.add(lic)
        await db_session.commit()
        await db_session.refresh(lic)
        codigos_creados.append(cod)
        return lic

    yield _factory

    await db_session.execute(
        delete(Licitacion).where(Licitacion.codigo.in_(codigos_creados))
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# Fixture: ticket cifrado para empresa
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_ticket(
    db_session: AsyncSession,
) -> AsyncGenerator[Callable[..., Any], None]:
    ticket_ids: list[uuid.UUID] = []

    async def _factory(
        empresa_id: uuid.UUID,
        ticket_plain: str = "TEST-TICKET-1234",
    ) -> TicketApi:
        existing = await db_session.execute(
            select(TicketApi).where(TicketApi.empresa_id == empresa_id)
        )
        existing_ticket = existing.scalar_one_or_none()
        if existing_ticket:
            return existing_ticket

        ticket = TicketApi(
            empresa_id=empresa_id,
            ticket_cifrado=encrypt_ticket(ticket_plain),
            ticket_ultimos_4=ticket_plain[-4:],
            status=TicketStatus.active,
        )
        db_session.add(ticket)
        await db_session.commit()
        await db_session.refresh(ticket)
        ticket_ids.append(ticket.id)
        return ticket

    yield _factory

    for tid in ticket_ids:
        t = await db_session.get(TicketApi, tid)
        if t is not None:
            await db_session.delete(t)
    await db_session.commit()


# ---------------------------------------------------------------------------
# Fixture: proveedor completo (usuario + empresa + ticket)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def proveedor_activo(
    make_user: Callable[..., Any],
    make_ticket: Callable[..., Any],
    db_session: AsyncSession,
) -> Any:
    """Proveedor con empresa y ticket activo, listo para usar la API."""
    user: Usuario = await make_user(
        email="e2e_proveedor@test.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        razon_social="E2E Test SpA",
    )
    result = await db_session.execute(
        select(Empresa).where(Empresa.usuario_id == user.id)
    )
    empresa: Empresa = result.scalar_one()
    ticket = await make_ticket(empresa.id)

    return {
        "usuario": user,
        "empresa": empresa,
        "ticket": ticket,
        "headers": auth_headers(user.id),
    }
