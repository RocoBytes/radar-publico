"""Tests unitarios para _sync_adjudicaciones (app/tasks/sync_detalle.py).

Valida la lógica de acumulación de montos por proveedor, idempotencia,
manejo de casos borde (None, listas vacías) y upsert de proveedor.

Usa BD de test real (NullPool — conftest patch_db_session).
Limpia manualmente toda fila creada al finalizar cada test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.models.adjudicacion import Adjudicacion
from app.models.enums import LicitacionEstado
from app.models.licitacion import Licitacion
from app.models.proveedor import Proveedor
from app.schemas.chilecompra import AdjudicacionItemAPI, FechasAPI, ItemListadoAPI
from app.tasks.sync_detalle import _sync_adjudicaciones

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid() -> str:
    """Genera un sufijo único de 6 hex para evitar colisiones entre tests."""
    return uuid.uuid4().hex[:6]


def _codigo_lic() -> str:
    return f"ADJ-{_uid()}-T26"


def _rut_prov() -> str:
    return f"76.{abs(uuid.uuid4().int) % 999_999:06d}-K"


def _make_licitacion(codigo: str) -> Licitacion:
    return Licitacion(
        codigo=codigo,
        nombre=f"Licitación test {codigo}",
        estado=LicitacionEstado.adjudicada,
        moneda="CLP",
    )


def _item(
    rut: str | None,
    nombre: str = "Proveedor Test",
    cantidad: float | None = 1.0,
    monto_unitario: float | None = 1000.0,
) -> ItemListadoAPI:
    """Construye un ItemListadoAPI con Adjudicacion para el proveedor dado."""
    adj: AdjudicacionItemAPI | None = None
    if rut is not None:
        adj = AdjudicacionItemAPI(
            RutProveedor=rut,
            NombreProveedor=nombre,
            Cantidad=cantidad,
            MontoUnitario=monto_unitario,
        )
    return ItemListadoAPI(Correlativo=1, Adjudicacion=adj)


def _item_sin_adj() -> ItemListadoAPI:
    """Item sin bloque de adjudicación."""
    return ItemListadoAPI(Correlativo=1, Adjudicacion=None)


def _fechas(adj: datetime | None = None) -> FechasAPI:
    return FechasAPI(
        FechaPublicacion=datetime(2026, 1, 1, tzinfo=UTC),
        FechaAdjudicacion=adj,
    )


# ---------------------------------------------------------------------------
# Fixtures de limpieza
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def limpiar_adjudicaciones_y_licitaciones(db_session: AsyncSession) -> None:
    """Limpia adjudicaciones y licitaciones de test antes de cada test.

    Proveedores se eliminan también para evitar colisiones de PK natural (rut).
    """
    await db_session.execute(delete(Adjudicacion))
    await db_session.execute(delete(Licitacion))
    await db_session.execute(delete(Proveedor))
    await db_session.commit()


# ---------------------------------------------------------------------------
# Caso 1: caso básico — 1 item válido → 1 Proveedor + 1 Adjudicacion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_basico_un_item_crea_proveedor_y_adjudicacion(
    db_session: AsyncSession,
) -> None:
    """1 ítem con adjudicación válida → se crean exactamente 1 Proveedor y 1 Adjudicacion."""
    codigo = _codigo_lic()
    rut = _rut_prov()

    db_session.add(_make_licitacion(codigo))
    await db_session.commit()

    items = [_item(rut=rut, cantidad=2.0, monto_unitario=500.0)]
    await _sync_adjudicaciones(db_session, codigo, items, _fechas())
    await db_session.commit()

    prov = await db_session.get(Proveedor, rut)
    assert prov is not None, "Proveedor debe existir en BD"

    rows = (
        (
            await db_session.execute(
                select(Adjudicacion).where(Adjudicacion.licitacion_codigo == codigo)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, "Debe haber exactamente 1 adjudicacion"
    assert rows[0].rut_proveedor == rut


# ---------------------------------------------------------------------------
# Caso 2: acumulación de monto — 2 items del mismo proveedor → suma correcta
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monto_acumulado_con_decimal_precision(
    db_session: AsyncSession,
) -> None:
    """2 ítems del mismo proveedor: 2x1000.5 + 3x500.25 = 3501.75 (sin pérdida float)."""
    codigo = _codigo_lic()
    rut = _rut_prov()

    db_session.add(_make_licitacion(codigo))
    await db_session.commit()

    items = [
        _item(rut=rut, cantidad=2.0, monto_unitario=1000.5),
        _item(rut=rut, cantidad=3.0, monto_unitario=500.25),
    ]
    await _sync_adjudicaciones(db_session, codigo, items, _fechas())
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(Adjudicacion).where(Adjudicacion.licitacion_codigo == codigo)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, "Un solo registro por proveedor"

    monto = rows[0].monto_adjudicado
    assert monto is not None
    # 2x1000.5 + 3x500.25 = 2001.0 + 1500.75 = 3501.75
    expected = Decimal("3501.75")
    assert monto == expected, f"Monto esperado {expected}, obtenido {monto}"


# ---------------------------------------------------------------------------
# Caso 3: múltiples proveedores → 2 filas de Adjudicacion separadas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiples_proveedores_dos_adjudicaciones(
    db_session: AsyncSession,
) -> None:
    """2 RutProveedor distintos → 2 Adjudicacion en BD, una por proveedor."""
    codigo = _codigo_lic()
    rut_a = _rut_prov()
    rut_b = _rut_prov()

    db_session.add(_make_licitacion(codigo))
    await db_session.commit()

    items = [
        _item(rut=rut_a, cantidad=1.0, monto_unitario=1000.0),
        _item(rut=rut_b, cantidad=1.0, monto_unitario=2000.0),
    ]
    await _sync_adjudicaciones(db_session, codigo, items, _fechas())
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(Adjudicacion).where(Adjudicacion.licitacion_codigo == codigo)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2, "Debe haber exactamente 2 adjudicaciones"

    ruts_en_bd = {r.rut_proveedor for r in rows}
    assert ruts_en_bd == {rut_a, rut_b}


# ---------------------------------------------------------------------------
# Caso 4: idempotencia — llamar dos veces → solo 1 Adjudicacion por proveedor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotencia_doble_llamada(
    db_session: AsyncSession,
) -> None:
    """Llamar _sync_adjudicaciones dos veces → DELETE+INSERT, no duplica filas."""
    codigo = _codigo_lic()
    rut = _rut_prov()

    db_session.add(_make_licitacion(codigo))
    await db_session.commit()

    items = [_item(rut=rut, cantidad=1.0, monto_unitario=1000.0)]

    # Primera llamada
    await _sync_adjudicaciones(db_session, codigo, items, _fechas())
    await db_session.commit()

    # Segunda llamada idéntica
    await _sync_adjudicaciones(db_session, codigo, items, _fechas())
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(Adjudicacion).where(Adjudicacion.licitacion_codigo == codigo)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, "Idempotente: debe haber exactamente 1 adjudicacion"


# ---------------------------------------------------------------------------
# Caso 5: items con Adjudicacion=None → no se insertan filas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_items_sin_adjudicacion_no_insertan(
    db_session: AsyncSession,
) -> None:
    """Items donde el bloque Adjudicacion es None → se ignoran, 0 filas en BD."""
    codigo = _codigo_lic()

    db_session.add(_make_licitacion(codigo))
    await db_session.commit()

    items = [_item_sin_adj(), _item_sin_adj()]
    await _sync_adjudicaciones(db_session, codigo, items, _fechas())
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(Adjudicacion).where(Adjudicacion.licitacion_codigo == codigo)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 0, "Sin adjudicaciones → tabla debe estar vacía para esta lic"


# ---------------------------------------------------------------------------
# Caso 6: RutProveedor=None → ítem ignorado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rut_proveedor_none_se_ignora(
    db_session: AsyncSession,
) -> None:
    """AdjudicacionItemAPI con RutProveedor=None → no se procesa, 0 filas."""
    codigo = _codigo_lic()

    db_session.add(_make_licitacion(codigo))
    await db_session.commit()

    items = [_item(rut=None)]
    await _sync_adjudicaciones(db_session, codigo, items, _fechas())
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(Adjudicacion).where(Adjudicacion.licitacion_codigo == codigo)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 0


# ---------------------------------------------------------------------------
# Caso 7: monto_total=None cuando Cantidad es None en el primer ítem
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monto_none_cuando_cantidad_es_none(
    db_session: AsyncSession,
) -> None:
    """Si el primer ítem del proveedor tiene Cantidad=None → monto_total=None."""
    codigo = _codigo_lic()
    rut = _rut_prov()

    db_session.add(_make_licitacion(codigo))
    await db_session.commit()

    # Primer ítem: Cantidad=None → monto queda None
    items = [_item(rut=rut, cantidad=None, monto_unitario=1000.0)]
    await _sync_adjudicaciones(db_session, codigo, items, _fechas())
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(Adjudicacion).where(Adjudicacion.licitacion_codigo == codigo)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].monto_adjudicado is None, "monto_adjudicado debe ser None"


# ---------------------------------------------------------------------------
# Caso 8: monto_total=None cuando MontoUnitario es None en el primer ítem
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monto_none_cuando_monto_unitario_es_none(
    db_session: AsyncSession,
) -> None:
    """Si el primer ítem del proveedor tiene MontoUnitario=None → monto_total=None."""
    codigo = _codigo_lic()
    rut = _rut_prov()

    db_session.add(_make_licitacion(codigo))
    await db_session.commit()

    items = [_item(rut=rut, cantidad=5.0, monto_unitario=None)]
    await _sync_adjudicaciones(db_session, codigo, items, _fechas())
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(Adjudicacion).where(Adjudicacion.licitacion_codigo == codigo)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].monto_adjudicado is None


# ---------------------------------------------------------------------------
# Caso 9: upsert proveedor — razon_social se actualiza si cambió
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_proveedor_upsert_actualiza_razon_social(
    db_session: AsyncSession,
) -> None:
    """Proveedor ya existe con nombre viejo → _sync_adjudicaciones actualiza razon_social."""
    codigo = _codigo_lic()
    rut = _rut_prov()

    # Insertar proveedor previo con nombre desactualizado
    prov_viejo = Proveedor(rut=rut, razon_social="Nombre Viejo SpA")
    db_session.add(prov_viejo)
    db_session.add(_make_licitacion(codigo))
    await db_session.commit()

    items = [
        ItemListadoAPI(
            Correlativo=1,
            Adjudicacion=AdjudicacionItemAPI(
                RutProveedor=rut,
                NombreProveedor="Nombre Nuevo Ltda",
                Cantidad=1.0,
                MontoUnitario=500.0,
            ),
        )
    ]
    await _sync_adjudicaciones(db_session, codigo, items, _fechas())
    await db_session.commit()

    # Refrescar desde BD
    db_session.expire_all()
    prov_actualizado = await db_session.get(Proveedor, rut)
    assert prov_actualizado is not None
    assert (
        prov_actualizado.razon_social == "Nombre Nuevo Ltda"
    ), f"razon_social debe ser 'Nombre Nuevo Ltda', era '{prov_actualizado.razon_social}'"


# ---------------------------------------------------------------------------
# Caso 10: lista vacía → nada insertado, sin error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lista_vacia_no_inserta_ni_falla(
    db_session: AsyncSession,
) -> None:
    """Lista de items vacía → función termina sin error, 0 adjudicaciones."""
    codigo = _codigo_lic()
    db_session.add(_make_licitacion(codigo))
    await db_session.commit()

    # No debe lanzar ninguna excepción
    await _sync_adjudicaciones(db_session, codigo, [], _fechas())
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(Adjudicacion).where(Adjudicacion.licitacion_codigo == codigo)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 0


# ---------------------------------------------------------------------------
# Caso 11: fecha_adjudicacion propagada desde FechasAPI a Adjudicacion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fecha_adjudicacion_propagada_desde_fechas(
    db_session: AsyncSession,
) -> None:
    """FechasAPI.FechaAdjudicacion se persiste en Adjudicacion.fecha_adjudicacion."""
    codigo = _codigo_lic()
    rut = _rut_prov()
    fecha_adj = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)

    db_session.add(_make_licitacion(codigo))
    await db_session.commit()

    items = [_item(rut=rut, cantidad=1.0, monto_unitario=1000.0)]
    fechas = FechasAPI(
        FechaPublicacion=datetime(2026, 1, 1, tzinfo=UTC),
        FechaAdjudicacion=fecha_adj,
    )
    await _sync_adjudicaciones(db_session, codigo, items, fechas)
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(Adjudicacion).where(Adjudicacion.licitacion_codigo == codigo)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1

    adj_fecha = rows[0].fecha_adjudicacion
    assert adj_fecha is not None, "fecha_adjudicacion no debe ser None"
    # Comparar componentes porque los tzinfo pueden diferir (aware vs naive UTC)
    assert adj_fecha.year == 2026
    assert adj_fecha.month == 3
    assert adj_fecha.day == 15
