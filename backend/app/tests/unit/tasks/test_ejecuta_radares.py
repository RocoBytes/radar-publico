"""Tests unitarios de _ejecutar_radar (tarea ejecuta_radares).

Usan BD de test (NullPool — conftest patch_db_session).
Se prueba el helper async directamente, sin invocar el wrapper Celery.

Casos cubiertos:
- Radar inexistente → stats vacíos.
- Radar inactivo → stats vacíos.
- Sin licitaciones nuevas después de ultima_ejecucion_at → 0 nuevos.
- Primera ejecución (ultima_ejecucion_at=None) con licitación reciente → nuevos=1.
- Idempotencia: segunda corrida → ya_existentes=1, nuevos=0.
- Filtro por q: solo licitaciones que coinciden en nombre.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

# ---------------------------------------------------------------------------
# Fixture de limpieza autouse
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _limpieza_licitaciones_radar(request: pytest.FixtureRequest) -> None:  # type: ignore[misc]
    """Borra filas de PipelineItem y Licitacion con código TEST-RADAR-*."""
    from app.db.session import AsyncSessionLocal
    from app.models.licitacion import Licitacion
    from app.models.pipeline import PipelineItem

    async def _borrar() -> None:
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(PipelineItem).where(PipelineItem.licitacion_codigo.like("TEST-RADAR-%"))
            )
            await session.execute(delete(Licitacion).where(Licitacion.codigo.like("TEST-RADAR-%")))
            await session.commit()

    await _borrar()
    yield  # type: ignore[misc]
    await _borrar()


# ---------------------------------------------------------------------------
# Fixtures de empresa y radar
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def empresa_radar_fixture() -> dict[str, object]:  # type: ignore[misc]
    """Crea Usuario + Empresa de prueba para tests de radar; limpia al finalizar."""
    from app.db.session import AsyncSessionLocal
    from app.models.empresa import Empresa
    from app.models.enums import UserRole, UserStatus
    from app.models.usuario import Usuario

    email = f"test_radar_{uuid.uuid4().hex[:8]}@test.cl"
    rut = f"76.{uuid.uuid4().int % 999_999:06d}-K"

    async with AsyncSessionLocal() as session:
        usuario = Usuario(
            email=email,
            password_hash="$2b$12$placeholder_no_se_usa",
            rol=UserRole.proveedor,
            status=UserStatus.active,
            must_change_password=False,
        )
        session.add(usuario)
        await session.flush()

        empresa = Empresa(
            usuario_id=usuario.id,
            rut=rut,
            razon_social="Empresa Radar Test SpA",
        )
        session.add(empresa)
        await session.commit()

        ids = {
            "usuario_id": usuario.id,
            "empresa_id": empresa.id,
        }

    yield ids  # type: ignore[misc]

    # Cascade desde Usuario borra Empresa → Radares → PipelineItems
    from app.db.session import AsyncSessionLocal as CleanupSession
    from app.models.usuario import Usuario as UsuarioModel

    async with CleanupSession() as session:
        u = await session.get(UsuarioModel, ids["usuario_id"])
        if u is not None:
            await session.delete(u)
            await session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _crear_licitacion_test(
    codigo: str,
    nombre: str = "Licitación Radar Test",
    fecha_publicacion: datetime | None = None,
) -> None:
    """Inserta una licitación mínima publicada usando ON CONFLICT DO NOTHING."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import LicitacionEstado
    from app.models.licitacion import Licitacion

    if fecha_publicacion is None:
        fecha_publicacion = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        stmt = (
            pg_insert(Licitacion)
            .values(
                codigo=codigo,
                nombre=nombre,
                estado=LicitacionEstado.publicada,
                moneda="CLP",
                fecha_publicacion=fecha_publicacion,
            )
            .on_conflict_do_nothing()
        )
        await session.execute(stmt)
        await session.commit()


async def _crear_radar(
    empresa_id: uuid.UUID,
    activo: bool = True,
    filtros: dict | None = None,
    ultima_ejecucion_at: datetime | None = None,
) -> uuid.UUID:
    """Crea un Radar y devuelve su id."""
    from app.db.session import AsyncSessionLocal
    from app.models.radar import Radar

    async with AsyncSessionLocal() as session:
        radar = Radar(
            empresa_id=empresa_id,
            nombre="Radar Test",
            activo=activo,
            filtros=filtros or {},
            ultima_ejecucion_at=ultima_ejecucion_at,
        )
        session.add(radar)
        await session.commit()
        return radar.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_radar_no_existe() -> None:
    """Radar con UUID inexistente → stats todos en cero sin error."""
    from app.tasks.ejecuta_radares import _ejecutar_radar

    radar_id = uuid.uuid4()
    result = await _ejecutar_radar(radar_id)

    assert result == {"nuevos": 0, "ya_existentes": 0, "errores": 0}


@pytest.mark.asyncio
async def test_radar_inactivo(empresa_radar_fixture: dict[str, object]) -> None:
    """Radar con activo=False → stats todos en cero, no procesa licitaciones."""
    from app.tasks.ejecuta_radares import _ejecutar_radar

    empresa_id: uuid.UUID = empresa_radar_fixture["empresa_id"]  # type: ignore[assignment]
    radar_id = await _crear_radar(empresa_id, activo=False)

    codigo = f"TEST-RADAR-{uuid.uuid4().hex[:6]}"
    await _crear_licitacion_test(codigo)

    result = await _ejecutar_radar(radar_id)

    assert result == {"nuevos": 0, "ya_existentes": 0, "errores": 0}


@pytest.mark.asyncio
async def test_sin_licitaciones_nuevas(
    empresa_radar_fixture: dict[str, object],
) -> None:
    """ultima_ejecucion_at=ahora() → ninguna licitación nueva → 0 nuevos."""
    from app.db.session import AsyncSessionLocal
    from app.models.radar import Radar
    from app.tasks.ejecuta_radares import _ejecutar_radar

    empresa_id: uuid.UUID = empresa_radar_fixture["empresa_id"]  # type: ignore[assignment]

    # Licitación publicada en el pasado (fuera de la ventana)
    codigo = f"TEST-RADAR-{uuid.uuid4().hex[:6]}"
    fecha_pasada = datetime.now(UTC) - timedelta(hours=48)
    await _crear_licitacion_test(codigo, fecha_publicacion=fecha_pasada)

    # Radar cuya última ejecución fue ahora → no debe detectar nada nuevo
    ultima = datetime.now(UTC)
    radar_id = await _crear_radar(empresa_id, ultima_ejecucion_at=ultima)

    result = await _ejecutar_radar(radar_id)

    assert result["nuevos"] == 0, f"No debe crear items, got: {result}"
    assert result["errores"] == 0

    # ultima_ejecucion_at debe haberse actualizado
    async with AsyncSessionLocal() as session:
        radar_db = await session.get(Radar, radar_id)
        assert radar_db is not None
        assert radar_db.ultima_ejecucion_at is not None
        # La nueva marca debe ser >= a la anterior
        assert radar_db.ultima_ejecucion_at >= ultima


@pytest.mark.asyncio
async def test_crea_pipeline_items(
    empresa_radar_fixture: dict[str, object],
) -> None:
    """ultima_ejecucion_at=None con licitación reciente → nuevos=1."""
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.pipeline import PipelineItem
    from app.models.radar import Radar
    from app.tasks.ejecuta_radares import _ejecutar_radar

    empresa_id: uuid.UUID = empresa_radar_fixture["empresa_id"]  # type: ignore[assignment]

    codigo = f"TEST-RADAR-{uuid.uuid4().hex[:6]}"
    await _crear_licitacion_test(codigo, fecha_publicacion=datetime.now(UTC))

    # Sin ultima_ejecucion_at → usa ventana de 24 h → incluye la licitación
    radar_id = await _crear_radar(empresa_id, ultima_ejecucion_at=None)

    result = await _ejecutar_radar(radar_id)

    assert result["nuevos"] == 1, f"Esperado nuevos=1, got: {result}"
    assert result["errores"] == 0

    # Verificar PipelineItem en la BD
    async with AsyncSessionLocal() as session:
        item = (
            await session.execute(
                select(PipelineItem).where(
                    PipelineItem.empresa_id == empresa_id,
                    PipelineItem.licitacion_codigo == codigo,
                )
            )
        ).scalar_one_or_none()
        assert item is not None, "Debe existir un PipelineItem tras la ejecución"

        radar_db = await session.get(Radar, radar_id)
        assert radar_db is not None
        assert radar_db.ultima_ejecucion_at is not None


@pytest.mark.asyncio
async def test_idempotente(empresa_radar_fixture: dict[str, object]) -> None:
    """Segunda ejecución: el outer query excluye licitaciones ya en pipeline → nuevos=0."""
    from sqlalchemy import func, select

    from app.db.session import AsyncSessionLocal
    from app.models.pipeline import PipelineItem
    from app.models.radar import Radar
    from app.tasks.ejecuta_radares import _ejecutar_radar

    empresa_id: uuid.UUID = empresa_radar_fixture["empresa_id"]  # type: ignore[assignment]

    codigo = f"TEST-RADAR-{uuid.uuid4().hex[:6]}"
    await _crear_licitacion_test(codigo, fecha_publicacion=datetime.now(UTC))

    radar_id = await _crear_radar(empresa_id, ultima_ejecucion_at=None)

    r1 = await _ejecutar_radar(radar_id)
    assert r1["nuevos"] == 1, f"Primera ejecución debe crear 1 item: {r1}"

    # Reiniciar ultima_ejecucion_at para que la ventana de 24 h aplique de nuevo
    async with AsyncSessionLocal() as session:
        radar_db = await session.get(Radar, radar_id)
        assert radar_db is not None
        radar_db.ultima_ejecucion_at = None
        await session.commit()

    # Segunda ejecución: ~exists() del outer query ya excluye la licitación
    r2 = await _ejecutar_radar(radar_id)
    assert r2["nuevos"] == 0, f"Segunda: no debe crear duplicados, got: {r2}"
    assert r2["errores"] == 0

    # Solo debe existir 1 PipelineItem en total (sin duplicados)
    async with AsyncSessionLocal() as session:
        count = (
            await session.execute(
                select(func.count()).where(
                    PipelineItem.empresa_id == empresa_id,
                    PipelineItem.licitacion_codigo == codigo,
                )
            )
        ).scalar()
        assert count == 1, f"No debe haber duplicados, got count={count}"


@pytest.mark.asyncio
async def test_filtro_q(empresa_radar_fixture: dict[str, object]) -> None:
    """Filtro q='tecnología': solo licitaciones cuyo nombre hace ilike match."""
    from sqlalchemy import func, select

    from app.db.session import AsyncSessionLocal
    from app.models.pipeline import PipelineItem
    from app.tasks.ejecuta_radares import _ejecutar_radar

    empresa_id: uuid.UUID = empresa_radar_fixture["empresa_id"]  # type: ignore[assignment]

    codigo_match = f"TEST-RADAR-{uuid.uuid4().hex[:6]}"
    codigo_no_match = f"TEST-RADAR-{uuid.uuid4().hex[:6]}"

    await _crear_licitacion_test(
        codigo_match,
        nombre="Proyecto tecnología educativa regional",
        fecha_publicacion=datetime.now(UTC),
    )
    await _crear_licitacion_test(
        codigo_no_match,
        nombre="Contrato de infraestructura vial",
        fecha_publicacion=datetime.now(UTC),
    )

    radar_id = await _crear_radar(
        empresa_id,
        filtros={"q": "tecnología"},
        ultima_ejecucion_at=None,
    )

    result = await _ejecutar_radar(radar_id)

    assert result["nuevos"] == 1, f"Solo debe coincidir 1 licitación, got: {result}"
    assert result["errores"] == 0

    # Verificar que el único PipelineItem apunta a la licitación correcta
    async with AsyncSessionLocal() as session:
        count_total = (
            await session.execute(select(func.count()).where(PipelineItem.empresa_id == empresa_id))
        ).scalar()
        assert count_total == 1, f"Esperado 1 PipelineItem, got {count_total}"

        item = (
            await session.execute(
                select(PipelineItem).where(
                    PipelineItem.empresa_id == empresa_id,
                    PipelineItem.licitacion_codigo == codigo_match,
                )
            )
        ).scalar_one_or_none()
        assert item is not None, f"El PipelineItem debe ser para {codigo_match}"
