"""Tests unitarios de _recalcula_empresa (tarea recalcula_scores).

Usan BD de test (NullPool — conftest patch_db_session).
Se prueba el helper async directamente, sin invocar el wrapper Celery.

Casos cubiertos:
- Empresa inexistente → stats vacíos.
- Empresa sin PipelineItems → stats vacíos.
- Score None → score calculado, actualizados=1.
- Score ya igual al calculado → sin_cambio=1.
- Idempotencia: segunda corrida sobre mismo estado → sin_cambio=1.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

# ---------------------------------------------------------------------------
# Fixture de limpieza autouse
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _limpieza_licitaciones_test(request: pytest.FixtureRequest) -> None:  # type: ignore[misc]
    """Borra filas de PipelineItem y Licitacion con código TEST-SCORE-*."""
    from app.db.session import AsyncSessionLocal
    from app.models.licitacion import Licitacion
    from app.models.pipeline import PipelineItem

    async def _borrar() -> None:
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(PipelineItem).where(
                    PipelineItem.licitacion_codigo.like("TEST-SCORE-%")
                )
            )
            await session.execute(
                delete(Licitacion).where(Licitacion.codigo.like("TEST-SCORE-%"))
            )
            await session.commit()

    await _borrar()
    yield  # type: ignore[misc]
    await _borrar()


# ---------------------------------------------------------------------------
# Fixture de empresa (crea usuario + empresa con cascade cleanup)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def empresa_fixture() -> dict[str, object]:  # type: ignore[misc]
    """Crea Usuario + Empresa de prueba; limpia al finalizar vía cascade."""
    from app.db.session import AsyncSessionLocal
    from app.models.empresa import Empresa
    from app.models.enums import UserRole, UserStatus
    from app.models.usuario import Usuario

    email = f"test_scores_{uuid.uuid4().hex[:8]}@test.cl"
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
            razon_social="Empresa Scores Test SpA",
        )
        session.add(empresa)
        await session.commit()

        ids = {
            "usuario_id": usuario.id,
            "empresa_id": empresa.id,
        }

    yield ids  # type: ignore[misc]

    # Cascade desde Usuario borra Empresa → PipelineItems
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


async def _crear_licitacion_test(codigo: str) -> None:
    """Inserta una licitación mínima usando ON CONFLICT DO NOTHING."""
    from app.db.session import AsyncSessionLocal
    from app.models.enums import LicitacionEstado
    from app.models.licitacion import Licitacion

    async with AsyncSessionLocal() as session:
        stmt = (
            pg_insert(Licitacion)
            .values(
                codigo=codigo,
                nombre=f"Licitación Test {codigo}",
                estado=LicitacionEstado.publicada,
                moneda="CLP",
            )
            .on_conflict_do_nothing()
        )
        await session.execute(stmt)
        await session.commit()


async def _crear_pipeline_item(
    empresa_id: uuid.UUID,
    licitacion_codigo: str,
    score: int | None = None,
) -> uuid.UUID:
    """Crea un PipelineItem y devuelve su id."""
    from app.db.session import AsyncSessionLocal
    from app.models.pipeline import PipelineItem

    async with AsyncSessionLocal() as session:
        item = PipelineItem(
            empresa_id=empresa_id,
            licitacion_codigo=licitacion_codigo,
            score=score,
        )
        session.add(item)
        await session.commit()
        return item.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empresa_no_existe() -> None:
    """Empresa con UUID inexistente → stats todos en cero sin error."""
    from app.tasks.recalcula_scores import _recalcula_empresa

    empresa_id = uuid.uuid4()
    result = await _recalcula_empresa(empresa_id)

    assert result == {"actualizados": 0, "sin_cambio": 0, "errores": 0}


@pytest.mark.asyncio
async def test_empresa_sin_items(empresa_fixture: dict[str, object]) -> None:
    """Empresa existente pero sin PipelineItems → stats todos en cero."""
    from app.tasks.recalcula_scores import _recalcula_empresa

    empresa_id: uuid.UUID = empresa_fixture["empresa_id"]  # type: ignore[assignment]
    result = await _recalcula_empresa(empresa_id)

    assert result == {"actualizados": 0, "sin_cambio": 0, "errores": 0}


@pytest.mark.asyncio
async def test_recalcula_score_nuevo(empresa_fixture: dict[str, object]) -> None:
    """PipelineItem con score=None → score calculado, actualizados=1."""
    from app.db.session import AsyncSessionLocal
    from app.models.pipeline import PipelineItem
    from app.tasks.recalcula_scores import _recalcula_empresa

    empresa_id: uuid.UUID = empresa_fixture["empresa_id"]  # type: ignore[assignment]
    codigo = f"TEST-SCORE-{uuid.uuid4().hex[:6]}"

    await _crear_licitacion_test(codigo)
    item_id = await _crear_pipeline_item(empresa_id, codigo, score=None)

    result = await _recalcula_empresa(empresa_id)

    assert result["actualizados"] == 1, f"Esperado actualizados=1, got: {result}"
    assert result["sin_cambio"] == 0
    assert result["errores"] == 0

    # Verificar que el score fue persistido en la BD
    async with AsyncSessionLocal() as session:
        item_db = await session.get(PipelineItem, item_id)
        assert item_db is not None
        assert item_db.score is not None, "El score debe haberse calculado y guardado"
        assert isinstance(item_db.score, int)


@pytest.mark.asyncio
async def test_score_sin_cambio(empresa_fixture: dict[str, object]) -> None:
    """Score ya igual al calculado → sin_cambio=1, actualizados=0."""
    from app.tasks.recalcula_scores import _recalcula_empresa

    empresa_id: uuid.UUID = empresa_fixture["empresa_id"]  # type: ignore[assignment]
    codigo = f"TEST-SCORE-{uuid.uuid4().hex[:6]}"

    await _crear_licitacion_test(codigo)
    await _crear_pipeline_item(empresa_id, codigo, score=None)

    # Primera corrida: fija el score en la BD
    primera = await _recalcula_empresa(empresa_id)
    assert primera["actualizados"] == 1, f"Primera: esperado actualizar, got: {primera}"

    # Segunda corrida: el score ya coincide → sin_cambio
    segunda = await _recalcula_empresa(empresa_id)
    assert segunda["sin_cambio"] == 1, f"Segunda: esperado sin_cambio, got: {segunda}"
    assert segunda["actualizados"] == 0


@pytest.mark.asyncio
async def test_idempotente(empresa_fixture: dict[str, object]) -> None:
    """Dos ejecuciones consecutivas: la segunda siempre retorna sin_cambio=1."""
    from app.tasks.recalcula_scores import _recalcula_empresa

    empresa_id: uuid.UUID = empresa_fixture["empresa_id"]  # type: ignore[assignment]
    codigo = f"TEST-SCORE-{uuid.uuid4().hex[:6]}"

    await _crear_licitacion_test(codigo)
    await _crear_pipeline_item(empresa_id, codigo, score=None)

    # Corrida 1: establece el score
    r1 = await _recalcula_empresa(empresa_id)
    assert r1["errores"] == 0, f"No deben haber errores en corrida 1: {r1}"

    # Corrida 2: idempotente
    r2 = await _recalcula_empresa(empresa_id)
    assert r2["sin_cambio"] == 1, f"Corrida 2 debe ser idempotente (sin_cambio=1): {r2}"
    assert r2["actualizados"] == 0
    assert r2["errores"] == 0
