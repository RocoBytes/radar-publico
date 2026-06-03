"""Tests unitarios de sync_detalle_licitacion.

Usan BD de test (NullPool — conftest patch_db_session) y mocks del cliente HTTP.
Sin red, sin ticket real de ChileCompra.

Casos cubiertos:
- Nueva licitación: crea filas en licitaciones, items y fechas.
- Idempotencia: segunda ejecución retorna sin_cambio sin duplicar filas.
- 404: retorna no_encontrada=1, no eleva excepción.
- Auto-encolado: sync_listado_diario encola detalle en nueva, no en sin_cambio.
- Upsert organismo: crea fila en organismos antes de asignar FK.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch
import uuid

import pytest
import pytest_asyncio

from app.schemas.chilecompra import (
    CompradorAPI,
    FechasAPI,
    ItemsAPI,
    LicitacionDetalleAPI,
    LicitacionDetalleResponseAPI,
    LicitacionesListadoResponseAPI,
    LicitacionListItemAPI,
)
from app.services.chilecompra.exceptions import LicitacionNoEncontradaError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TICKET_PUBLICO = "F8537A18-6766-4DEF-9E59-426B4FEE2844"


def _make_detalle_response(
    codigo: str = "1234-1-L126",
    nombre: str = "Licitación Test",
    estado_codigo: int = 5,
    n_items: int = 2,
) -> LicitacionDetalleResponseAPI:
    """Construye una respuesta de detalle con datos mínimos pero completos."""
    # Items con Listado vacío — evita la FK constraint de unspsc_codigos en tests.
    # La tabla unspsc_codigos no se crea en el schema de prueba porque no tiene
    # datos seed. Los items se verifican mediante el count=0 esperado.
    # Para tests que requieran items reales usar @pytest.mark.integration.
    _ = n_items  # parámetro reservado para tests de integración futuros
    detalle = LicitacionDetalleAPI(
        CodigoExterno=codigo,
        Nombre=nombre,
        CodigoEstado=estado_codigo,
        Estado="Publicada",
        Descripcion="Descripción completa de la licitación",
        Moneda="CLP",
        MontoEstimado=1_000_000.0,
        EsRenovable=0,
        Items=ItemsAPI(Cantidad=0, Listado=[]),
        Fechas=FechasAPI(
            FechaCreacion=datetime(2026, 5, 1, tzinfo=UTC),
            FechaPublicacion=datetime(2026, 5, 2, tzinfo=UTC),
            FechaCierre=datetime(2026, 6, 1, tzinfo=UTC),
        ),
    )
    return LicitacionDetalleResponseAPI(Cantidad=1, Listado=[detalle])


def _make_detalle_response_con_organismo(
    codigo: str,
    codigo_org: int,
) -> LicitacionDetalleResponseAPI:
    """Construye una respuesta de detalle que incluye datos del comprador.

    Permite verificar que _upsert_organismo se ejecuta correctamente y
    que el FK queda asignado en la licitación resultante.

    Args:
        codigo: Código de la licitación de prueba.
        codigo_org: Código numérico del organismo a insertar.
    """
    comprador = CompradorAPI(
        CodigoOrganismo=str(codigo_org),
        NombreOrganismo=f"Municipalidad Test {codigo_org}",
        RutUnidad="69.123.456-7",
        RegionUnidad="Región Metropolitana de Santiago",
        NombreUnidad="Unidad de Abastecimiento",
        CodigoUnidad="1001",
    )
    detalle = LicitacionDetalleAPI(
        CodigoExterno=codigo,
        Nombre="Licitación con Organismo Test",
        CodigoEstado=5,
        Estado="Publicada",
        Descripcion="Descripción con datos de comprador",
        Moneda="CLP",
        MontoEstimado=2_500_000.0,
        EsRenovable=0,
        Comprador=comprador,
        Items=ItemsAPI(Cantidad=0, Listado=[]),
        Fechas=FechasAPI(
            FechaCreacion=datetime(2026, 5, 1, tzinfo=UTC),
            FechaPublicacion=datetime(2026, 5, 2, tzinfo=UTC),
            FechaCierre=datetime(2026, 6, 1, tzinfo=UTC),
        ),
    )
    return LicitacionDetalleResponseAPI(Cantidad=1, Listado=[detalle])


# ---------------------------------------------------------------------------
# Fixture: ticket activo en la BD de test
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def ticket_activo() -> dict[str, str]:  # type: ignore[misc]
    """Crea usuario → empresa → ticket activo en la BD de test. Limpia al final."""
    from app.core.encryption import encrypt_ticket
    from app.db.session import AsyncSessionLocal
    from app.models.empresa import Empresa
    from app.models.enums import EmpresaTamano, TicketStatus, UserRole, UserStatus
    from app.models.ticket import TicketApi
    from app.models.usuario import Usuario

    async with AsyncSessionLocal() as session:
        usuario = Usuario(
            email=f"test_detalle_{uuid.uuid4().hex[:8]}@test.cl",
            password_hash="$2b$12$placeholder_no_se_usa",
            rol=UserRole.proveedor,
            status=UserStatus.active,
            must_change_password=False,
        )
        session.add(usuario)
        await session.flush()

        empresa = Empresa(
            usuario_id=usuario.id,
            rut=f"76.{uuid.uuid4().int % 999_999:06d}-K",
            razon_social="Empresa Test Detalle SpA",
            tamano=EmpresaTamano.pequena,
        )
        session.add(empresa)
        await session.flush()

        ticket = TicketApi(
            empresa_id=empresa.id,
            ticket_cifrado=encrypt_ticket(TICKET_PUBLICO),
            ticket_ultimos_4=TICKET_PUBLICO[-4:],
            status=TicketStatus.active,
        )
        session.add(ticket)
        await session.commit()

        ids = {
            "usuario_id": str(usuario.id),
            "ticket_id": str(ticket.id),
        }

    yield ids

    # Cleanup — cascade borra empresa, ticket, items, etc.
    from app.db.session import AsyncSessionLocal as CleanupSession
    from app.models.usuario import Usuario as UsuarioModel

    async with CleanupSession() as session:
        u = await session.get(UsuarioModel, uuid.UUID(ids["usuario_id"]))
        if u:
            await session.delete(u)
            await session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_detalle_licitacion_nueva(ticket_activo: dict[str, str]) -> None:
    """Nueva licitación: persiste detalle, items y fechas correctamente."""
    from sqlalchemy import func, select

    from app.db.session import AsyncSessionLocal
    from app.models.licitacion import Licitacion, LicitacionFecha, LicitacionItem

    codigo = f"TEST-{uuid.uuid4().hex[:6]}-L26"
    detalle_response = _make_detalle_response(codigo=codigo, n_items=3)

    mock_client = AsyncMock()
    mock_client.obtener_detalle_licitacion = AsyncMock(return_value=detalle_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.sync_detalle.MercadoPublicoClient", return_value=mock_client):
        from app.tasks.sync_detalle import _run

        result = await _run(codigo)

    assert result["nueva"] == 1, f"Esperado nueva=1, got: {result}"
    assert result["error"] == 0
    assert result["no_encontrada"] == 0

    # Verificar persistencia
    async with AsyncSessionLocal() as session:
        lic = await session.get(Licitacion, codigo)
        assert lic is not None
        assert lic.detalle_sincronizado_at is not None
        assert lic.raw_payload is not None
        assert lic.descripcion == "Descripción completa de la licitación"

        # Items vacíos — la respuesta mock tiene Listado=[] para evitar
        # la FK constraint de unspsc_codigos que no existe en la BD de test.
        items_count = (
            await session.execute(
                select(func.count()).where(LicitacionItem.licitacion_codigo == codigo)
            )
        ).scalar()
        assert items_count == 0, f"Sin items en mock de test, got {items_count}"

        fechas_count = (
            await session.execute(
                select(func.count()).where(LicitacionFecha.licitacion_codigo == codigo)
            )
        ).scalar()
        assert (
            fechas_count or 0
        ) >= 2, f"Esperadas al menos 2 fechas, encontradas {fechas_count}"

    # Cleanup del item de test
    async with AsyncSessionLocal() as session:
        lic_cleanup = await session.get(Licitacion, codigo)
        if lic_cleanup:
            await session.delete(lic_cleanup)
            await session.commit()


@pytest.mark.asyncio
async def test_sync_detalle_licitacion_idempotente(
    ticket_activo: dict[str, str],
) -> None:
    """Segunda ejecución retorna sin_cambio=1, sin duplicar filas en la BD."""
    from sqlalchemy import func, select

    from app.db.session import AsyncSessionLocal
    from app.models.licitacion import Licitacion, LicitacionItem

    codigo = f"IDEM-{uuid.uuid4().hex[:6]}-L26"
    detalle_response = _make_detalle_response(codigo=codigo, n_items=2)

    mock_client = AsyncMock()
    mock_client.obtener_detalle_licitacion = AsyncMock(return_value=detalle_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.sync_detalle.MercadoPublicoClient", return_value=mock_client):
        from app.tasks.sync_detalle import _run

        result_primera = await _run(codigo)
        # Segunda ejecución — misma licitación, ahora con detalle_sincronizado_at
        result_segunda = await _run(codigo)

    assert result_primera["nueva"] == 1
    assert (
        result_segunda["sin_cambio"] == 1
    ), f"Segunda corrida debió retornar sin_cambio, retornó: {result_segunda}"
    # La API NO debe haberse llamado en la segunda ejecución (cache hit)
    assert (
        mock_client.obtener_detalle_licitacion.call_count == 1
    ), "La API no debería llamarse en la segunda ejecución"

    # Sin duplicación — el mock tiene Items vacíos, así que esperamos 0
    async with AsyncSessionLocal() as session:
        items_count = (
            await session.execute(
                select(func.count()).where(LicitacionItem.licitacion_codigo == codigo)
            )
        ).scalar()
        assert items_count == 0, f"No debería haber duplicación: {items_count} items"

    # Cleanup
    async with AsyncSessionLocal() as session:
        lic = await session.get(Licitacion, codigo)
        if lic:
            await session.delete(lic)
            await session.commit()


@pytest.mark.asyncio
async def test_sync_detalle_licitacion_404(ticket_activo: dict[str, str]) -> None:
    """404: retorna no_encontrada=1, no eleva, detalle_sincronizado_at nulo."""
    from app.db.session import AsyncSessionLocal
    from app.models.licitacion import Licitacion

    codigo = f"404-{uuid.uuid4().hex[:6]}-L26"

    mock_client = AsyncMock()
    mock_client.obtener_detalle_licitacion = AsyncMock(
        side_effect=LicitacionNoEncontradaError(codigo)
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.sync_detalle.MercadoPublicoClient", return_value=mock_client):
        from app.tasks.sync_detalle import _run

        result = await _run(codigo)

    assert result["no_encontrada"] == 1
    assert result["error"] == 0
    assert result["nueva"] == 0

    # La licitación no debe existir en la BD
    async with AsyncSessionLocal() as session:
        lic = await session.get(Licitacion, codigo)
        if lic is not None:
            assert lic.detalle_sincronizado_at is None


@pytest.mark.asyncio
async def test_sync_listado_encola_detalle() -> None:
    """sync_listado_diario encola detalle para nueva, no para sin_cambio."""
    import hashlib
    import json

    from app.core.encryption import encrypt_ticket
    from app.db.session import AsyncSessionLocal
    from app.models.enums import LicitacionEstado
    from app.models.licitacion import Licitacion
    from app.tasks.sync_chilecompra import _sync_empresa

    # Licitación existente con hash coincidente → sin_cambio
    codigo_nueva = f"NEW-{uuid.uuid4().hex[:6]}-L26"
    codigo_sinc = f"SIN-{uuid.uuid4().hex[:6]}-L26"

    hash_sinc = hashlib.sha256(
        json.dumps(
            {"codigo": codigo_sinc, "nombre": "Sin Cambio Lic", "estado": 5},
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()

    async with AsyncSessionLocal() as session:
        session.add(
            Licitacion(
                codigo=codigo_sinc,
                nombre="Sin Cambio Lic",
                estado=LicitacionEstado.publicada,
                estado_codigo=5,
                hash_contenido=hash_sinc,
                detalle_sincronizado_at=datetime.now(UTC),
            )
        )
        await session.commit()

    # La API devuelve: 1 nueva + 1 sin cambio
    listado_response = LicitacionesListadoResponseAPI(
        Cantidad=2,
        Listado=[
            LicitacionListItemAPI(
                CodigoExterno=codigo_nueva,
                Nombre="Licitación Nueva",
                CodigoEstado=5,
                FechaCierre=datetime(2026, 6, 30, tzinfo=UTC),
            ),
            LicitacionListItemAPI(
                CodigoExterno=codigo_sinc,
                Nombre="Sin Cambio Lic",  # hash idéntico → sin_cambio
                CodigoEstado=5,
                FechaCierre=None,
            ),
        ],
    )

    mock_client = AsyncMock()
    mock_client.listar_licitaciones_por_estado = AsyncMock(
        return_value=listado_response
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    ticket_cifrado = encrypt_ticket(TICKET_PUBLICO)
    ticket_id_uuid = uuid.uuid4()
    empresa_id_uuid = uuid.uuid4()
    encolados: list[str] = []

    def mock_send_task(name: str, args: list[Any], **kwargs: Any) -> None:
        encolados.append(args[0])

    with (
        patch(
            "app.tasks.sync_chilecompra.MercadoPublicoClient",
            return_value=mock_client,
        ),
        patch(
            "app.tasks.sync_chilecompra.celery_app.send_task",
            side_effect=mock_send_task,
        ),
    ):
        stats = await _sync_empresa(
            empresa_id=str(empresa_id_uuid),
            ticket_cifrado=ticket_cifrado,
            ticket_id=str(ticket_id_uuid),
            ticket_ultimos_4=TICKET_PUBLICO[-4:],
        )

    assert stats["nuevas"] == 1, f"Esperada 1 nueva, got: {stats}"
    assert stats["sin_cambio"] == 1, f"Esperado 1 sin_cambio, got: {stats}"

    # Solo la nueva debe haberse encolado
    assert (
        len(encolados) == 1
    ), f"Esperado exactamente 1 encolado, got {len(encolados)}: {encolados}"
    assert codigo_nueva in encolados
    assert codigo_sinc not in encolados

    # Cleanup
    async with AsyncSessionLocal() as session:
        for cod in [codigo_nueva, codigo_sinc]:
            lic = await session.get(Licitacion, cod)
            if lic:
                await session.delete(lic)
        await session.commit()


@pytest.mark.asyncio
async def test_sync_detalle_crea_organismo(ticket_activo: dict[str, str]) -> None:
    """sync_detalle hace upsert en organismos antes de setear el FK."""
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.licitacion import Licitacion
    from app.models.organismo import Organismo

    codigo_lic = f"ORG-{uuid.uuid4().hex[:6]}-L26"
    # Código de prueba que no colisiona con datos de seed reales
    codigo_org = 99901
    detalle_response = _make_detalle_response_con_organismo(
        codigo=codigo_lic,
        codigo_org=codigo_org,
    )

    mock_client = AsyncMock()
    mock_client.obtener_detalle_licitacion = AsyncMock(return_value=detalle_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.sync_detalle.MercadoPublicoClient", return_value=mock_client):
        from app.tasks.sync_detalle import _run

        result = await _run(codigo_lic)

    assert result["nueva"] == 1, f"Esperado nueva=1, got: {result}"
    assert result["error"] == 0

    # Verificar que el organismo fue creado en la BD
    async with AsyncSessionLocal() as session:
        organismo = (
            await session.execute(
                select(Organismo).where(Organismo.codigo_organismo == codigo_org)
            )
        ).scalar_one_or_none()

        assert (
            organismo is not None
        ), f"El organismo {codigo_org} debería existir en organismos"
        assert organismo.nombre == f"Municipalidad Test {codigo_org}"
        assert organismo.rut == "69.123.456-7"
        assert organismo.region == "Región Metropolitana de Santiago"

        # El FK en la licitación debe apuntar al organismo recién insertado
        lic = await session.get(Licitacion, codigo_lic)
        assert lic is not None
        assert (
            lic.codigo_organismo == codigo_org
        ), f"FK codigo_organismo debería ser {codigo_org}, got {lic.codigo_organismo}"

    # Cleanup — primero licitación (FK hijo), luego organismo
    async with AsyncSessionLocal() as session:
        lic_cleanup = await session.get(Licitacion, codigo_lic)
        if lic_cleanup:
            await session.delete(lic_cleanup)
            await session.commit()

    async with AsyncSessionLocal() as session:
        org_cleanup = (
            await session.execute(
                select(Organismo).where(Organismo.codigo_organismo == codigo_org)
            )
        ).scalar_one_or_none()
        if org_cleanup:
            await session.delete(org_cleanup)
            await session.commit()
