"""Tests unitarios de detecta_renovaciones (tarea Celery).

Usan BD de test (NullPool — conftest patch_db_session).
Se prueba el helper async _run() directamente.

Casos cubiertos:
- Sin empresas con ticket activo → 0 notificaciones.
- Empresa con licitación renovable dentro del horizonte → crea notif.
- Idempotencia: segunda corrida no duplica notif dentro del período de dedup.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

# ---------------------------------------------------------------------------
# Fixtures de limpieza
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _limpieza() -> None:  # type: ignore[misc]
    from app.db.session import AsyncSessionLocal
    from app.models.licitacion import Licitacion
    from app.models.notificacion import Notificacion

    async def _borrar() -> None:
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(Notificacion).where(Notificacion.licitacion_codigo.like("TEST-RENOV-%"))
            )
            await session.execute(delete(Licitacion).where(Licitacion.codigo.like("TEST-RENOV-%")))
            await session.commit()

    await _borrar()
    yield  # type: ignore[misc]
    await _borrar()


@pytest_asyncio.fixture
async def empresa_con_ticket() -> dict[str, object]:  # type: ignore[misc]
    """Crea Usuario + Empresa + TicketApi activo. Limpia al finalizar."""
    from app.core.encryption import encrypt_ticket
    from app.db.session import AsyncSessionLocal
    from app.models.empresa import Empresa
    from app.models.enums import (
        EmpresaTamano,
        TicketStatus,
        UserRole,
        UserStatus,
    )
    from app.models.ticket import TicketApi
    from app.models.usuario import Usuario

    email = f"test_renov_{uuid.uuid4().hex[:8]}@test.cl"
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
            razon_social="Empresa Renov Test SpA",
            tamano=EmpresaTamano.pequena,
        )
        session.add(empresa)
        await session.flush()

        ticket = TicketApi(
            empresa_id=empresa.id,
            ticket_cifrado=encrypt_ticket("TICKET-TEST-RENOV"),
            ticket_ultimos_4="ENOV",
            status=TicketStatus.active,
        )
        session.add(ticket)
        await session.commit()

        ids = {
            "usuario_id": usuario.id,
            "empresa_id": empresa.id,
            "ticket_id": ticket.id,
        }

    yield ids  # type: ignore[misc]

    from app.db.session import AsyncSessionLocal as CleanupSession
    from app.models.usuario import Usuario as UsuarioModel

    async with CleanupSession() as session:
        u = await session.get(UsuarioModel, ids["usuario_id"])
        if u is not None:
            await session.delete(u)
            await session.commit()


async def _crear_licitacion_renovable_para(
    empresa_id: object,
    *,
    codigo: str = "TEST-RENOV-001",
    dias_termino: int = 60,
) -> None:
    from app.db.session import AsyncSessionLocal
    from app.models.enums import LicitacionEstado
    from app.models.licitacion import Licitacion

    ahora = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        lic = Licitacion(
            codigo=codigo,
            nombre=f"Licitación renovable {codigo}",
            estado=LicitacionEstado.adjudicada,
            es_renovable=True,
            fecha_estimada_termino_contrato=ahora + timedelta(days=dias_termino),
        )
        session.add(lic)
        await session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sin_empresas_activas() -> None:
    """Sin tickets activos → sin notificaciones creadas."""
    from app.tasks.detecta_renovaciones import _run

    result = await _run()
    assert result["notificaciones_creadas"] == 0
    assert result["empresas"] == 0


@pytest.mark.asyncio
async def test_crea_notificacion_por_renovacion(
    empresa_con_ticket: dict[str, object],
) -> None:
    """Licitación renovable dentro del horizonte genera notif in_app."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifTipo
    from app.models.notificacion import Notificacion
    from app.tasks.detecta_renovaciones import _run

    empresa_id = empresa_con_ticket["empresa_id"]
    await _crear_licitacion_renovable_para(empresa_id, codigo="TEST-RENOV-001", dias_termino=60)

    result = await _run()
    assert result["notificaciones_creadas"] >= 1

    async with AsyncSessionLocal() as session:
        notif_r = await session.execute(
            select(Notificacion).where(
                Notificacion.empresa_id == empresa_id,
                Notificacion.tipo == NotifTipo.oportunidad_futura,
                Notificacion.licitacion_codigo == "TEST-RENOV-001",
            )
        )
        notif = notif_r.scalar_one_or_none()
    assert notif is not None
    assert "TEST-RENOV-001" in notif.cuerpo
    assert notif.datos.get("dias_para_termino") is not None


@pytest.mark.asyncio
async def test_idempotente_no_duplica(
    empresa_con_ticket: dict[str, object],
) -> None:
    """Segunda ejecución no duplica la notificación dentro del período de dedup."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifTipo
    from app.models.notificacion import Notificacion
    from app.tasks.detecta_renovaciones import _run

    empresa_id = empresa_con_ticket["empresa_id"]
    await _crear_licitacion_renovable_para(empresa_id, codigo="TEST-RENOV-002", dias_termino=45)

    await _run()
    await _run()

    async with AsyncSessionLocal() as session:
        count_r = await session.execute(
            select(Notificacion).where(
                Notificacion.empresa_id == empresa_id,
                Notificacion.tipo == NotifTipo.oportunidad_futura,
                Notificacion.licitacion_codigo == "TEST-RENOV-002",
            )
        )
        notifs = count_r.scalars().all()

    assert len(notifs) == 1, f"Esperaba 1 notificación, encontré {len(notifs)}"


@pytest.mark.asyncio
async def test_no_notifica_fuera_del_horizonte(
    empresa_con_ticket: dict[str, object],
) -> None:
    """Licitación cuyo término está más allá de 180 días no genera notificación."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import NotifTipo
    from app.models.notificacion import Notificacion
    from app.tasks.detecta_renovaciones import _run

    empresa_id = empresa_con_ticket["empresa_id"]
    await _crear_licitacion_renovable_para(empresa_id, codigo="TEST-RENOV-003", dias_termino=400)

    await _run()

    async with AsyncSessionLocal() as session:
        notif_r = await session.execute(
            select(Notificacion).where(
                Notificacion.licitacion_codigo == "TEST-RENOV-003",
                Notificacion.tipo == NotifTipo.oportunidad_futura,
            )
        )
        notif = notif_r.scalar_one_or_none()

    assert notif is None
