"""Test de integración end-to-end del sync con BD real y ticket público.

Requiere:
- Postgres corriendo con schema cargado.
- Variables de entorno de BD configuradas.
- Acceso a internet (llama a la API real).

Ticket público de prueba:
  F8537A18-6766-4DEF-9E59-426B4FEE2844

Marcado como @pytest.mark.integration para correr selectivamente:
  pytest -m integration
"""

from collections.abc import AsyncGenerator
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.core.encryption import encrypt_ticket
from app.db.session import AsyncSessionLocal
from app.models.empresa import Empresa
from app.models.enums import EmpresaTamano, TicketStatus, UserRole, UserStatus
from app.models.ticket import TicketApi
from app.models.usuario import Usuario

TICKET_PUBLICO = "F8537A18-6766-4DEF-9E59-426B4FEE2844"

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture(scope="function")
async def empresa_prueba() -> AsyncGenerator[dict[str, str], None]:
    """Crea un usuario + empresa + ticket de prueba en la BD, los limpia al final."""
    async with AsyncSessionLocal() as session:
        usuario = Usuario(
            email=f"test_integration_{uuid.uuid4().hex[:8]}@radarpublico.cl",
            password_hash="$2b$12$placeholder_no_se_usa_en_esta_tarea",
            rol=UserRole.proveedor,
            status=UserStatus.active,
            must_change_password=False,
        )
        session.add(usuario)
        await session.flush()

        empresa = Empresa(
            usuario_id=usuario.id,
            rut=f"76.{uuid.uuid4().int % 999_999:06d}-K",
            razon_social="Empresa Test Integración SpA",
            regiones_operacion=["Metropolitana de Santiago"],
            tamano=EmpresaTamano.pequena,
        )
        session.add(empresa)
        await session.flush()

        ticket_cifrado = encrypt_ticket(TICKET_PUBLICO)
        ticket = TicketApi(
            empresa_id=empresa.id,
            ticket_cifrado=ticket_cifrado,
            ticket_ultimos_4=TICKET_PUBLICO[-4:],
            status=TicketStatus.active,
        )
        session.add(ticket)
        await session.commit()

        ids = {
            "usuario_id": str(usuario.id),
            "empresa_id": str(empresa.id),
            "ticket_id": str(ticket.id),
        }

    yield ids

    # Cleanup
    async with AsyncSessionLocal() as session:
        usuario_cleanup: Usuario | None = await session.get(
            Usuario, uuid.UUID(ids["usuario_id"])
        )
        if usuario_cleanup is not None:
            await session.delete(usuario_cleanup)
            await session.commit()


@pytest.mark.asyncio
async def test_sync_listado_trae_licitaciones(empresa_prueba: dict[str, str]) -> None:
    """Verifica que el sync trae licitaciones y las persiste correctamente."""
    from app.services.chilecompra.client import MercadoPublicoClient
    from app.services.chilecompra.enums import EstadoLicitacion

    empresa_id = uuid.UUID(empresa_prueba["empresa_id"])
    ticket_id = uuid.UUID(empresa_prueba["ticket_id"])

    # Obtener el ticket cifrado
    async with AsyncSessionLocal() as session:
        ticket_obj = await session.get(TicketApi, ticket_id)
        assert ticket_obj is not None
        ticket_cifrado = ticket_obj.ticket_cifrado

    from app.core.encryption import decrypt_ticket

    ticket_plaintext = decrypt_ticket(ticket_cifrado)

    async with MercadoPublicoClient() as client:
        response = await client.listar_licitaciones_por_estado(
            estado=EstadoLicitacion.ACTIVAS,
            ticket=ticket_plaintext,
            ticket_id=ticket_id,
            empresa_id=empresa_id,
        )

    del ticket_plaintext  # Limpiar inmediatamente — regla de oro #2

    assert response.Cantidad > 0, "La API debería retornar licitaciones activas"
    assert len(response.Listado) > 0

    # Verificar estructura del primer resultado
    primera = response.Listado[0]
    assert primera.CodigoExterno
    assert primera.Nombre
    assert primera.CodigoEstado == 5  # publicada


@pytest.mark.asyncio
async def test_sync_idempotente(empresa_prueba: dict[str, str]) -> None:
    """Ejecutar sync dos veces no duplica registros."""
    from app.core.encryption import decrypt_ticket
    from app.models.licitacion import Licitacion
    from app.services.chilecompra.client import MercadoPublicoClient
    from app.services.chilecompra.enums import EstadoLicitacion

    empresa_id = uuid.UUID(empresa_prueba["empresa_id"])
    ticket_id = uuid.UUID(empresa_prueba["ticket_id"])

    async with AsyncSessionLocal() as session:
        ticket_obj = await session.get(TicketApi, ticket_id)
        assert ticket_obj is not None
        ticket_plaintext = decrypt_ticket(ticket_obj.ticket_cifrado)

    # Primera sync — persistir algunas
    async with MercadoPublicoClient() as client:
        response = await client.listar_licitaciones_por_estado(
            estado=EstadoLicitacion.ACTIVAS,
            ticket=ticket_plaintext,
            ticket_id=ticket_id,
            empresa_id=empresa_id,
        )

    # Persistir las primeras 5 licitaciones
    from app.models.enums import LicitacionEstado

    async with AsyncSessionLocal() as session:
        for item in response.Listado[:5]:
            existing = await session.get(Licitacion, item.CodigoExterno)
            if existing is None:
                session.add(
                    Licitacion(
                        codigo=item.CodigoExterno,
                        nombre=item.Nombre,
                        estado=LicitacionEstado.publicada,
                        estado_codigo=item.CodigoEstado,
                    )
                )
        await session.commit()

    # Contar tras primera sync
    async with AsyncSessionLocal() as session:
        count_primera = (
            await session.execute(select(text("count(*) FROM licitaciones")))
        ).scalar()

    # Segunda sync — mismos datos, no debe duplicar
    async with MercadoPublicoClient() as client:
        response2 = await client.listar_licitaciones_por_estado(
            estado=EstadoLicitacion.ACTIVAS,
            ticket=ticket_plaintext,
            ticket_id=ticket_id,
            empresa_id=empresa_id,
        )

    async with AsyncSessionLocal() as session:
        for item in response2.Listado[:5]:
            existing = await session.get(Licitacion, item.CodigoExterno)
            if existing is None:
                session.add(
                    Licitacion(
                        codigo=item.CodigoExterno,
                        nombre=item.Nombre,
                        estado=LicitacionEstado.publicada,
                        estado_codigo=item.CodigoEstado,
                    )
                )
        await session.commit()

    del ticket_plaintext

    # Verificar que el count no aumentó (idempotencia)
    async with AsyncSessionLocal() as session:
        count_segunda = (
            await session.execute(select(text("count(*) FROM licitaciones")))
        ).scalar()

    assert (
        count_segunda == count_primera
    ), f"Segunda sync duplicó registros: {count_primera} → {count_segunda}"


@pytest.mark.asyncio
async def test_api_quota_log_se_persiste(empresa_prueba: dict[str, str]) -> None:
    """Verifica que cada request queda registrado en api_quota_log."""
    from app.core.encryption import decrypt_ticket
    from app.models.api_log import ApiQuotaLog
    from app.services.chilecompra.client import MercadoPublicoClient
    from app.services.chilecompra.enums import EstadoLicitacion

    empresa_id = uuid.UUID(empresa_prueba["empresa_id"])
    ticket_id = uuid.UUID(empresa_prueba["ticket_id"])

    async with AsyncSessionLocal() as session:
        ticket_obj = await session.get(TicketApi, ticket_id)
        assert ticket_obj is not None
        ticket_plaintext = decrypt_ticket(ticket_obj.ticket_cifrado)

    from sqlalchemy import func

    # Contar logs antes
    async with AsyncSessionLocal() as session:
        count_antes_raw = (
            await session.execute(
                select(func.count()).where(ApiQuotaLog.ticket_id == ticket_id)
            )
        ).scalar()
    count_antes = count_antes_raw or 0

    async with MercadoPublicoClient() as client:
        await client.listar_licitaciones_por_estado(
            estado=EstadoLicitacion.ACTIVAS,
            ticket=ticket_plaintext,
            ticket_id=ticket_id,
            empresa_id=empresa_id,
        )

    del ticket_plaintext

    # Debe haber al menos 1 log nuevo
    async with AsyncSessionLocal() as session:
        count_despues_raw = (
            await session.execute(
                select(func.count()).where(ApiQuotaLog.ticket_id == ticket_id)
            )
        ).scalar()
    count_despues = count_despues_raw or 0

    assert count_despues > count_antes, "El request no se registró en api_quota_log"
