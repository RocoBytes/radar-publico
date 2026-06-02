"""Backfill one-shot de adjudicaciones desde raw_payload.

Procesa todas las licitaciones adjudicadas (CodigoEstado=8) que tienen
raw_payload en BD pero ninguna fila en la tabla adjudicaciones.

No hace ninguna llamada a la API de ChileCompra — re-parsea los datos
JSON ya almacenados usando los schemas actualizados (AdjudicacionItemAPI).

Uso:
    docker compose exec api python -m app.scripts.backfill_adjudicaciones
    docker compose exec api python -m app.scripts.backfill_adjudicaciones --limit 1000
    docker compose exec api python -m app.scripts.backfill_adjudicaciones --dry-run

Es idempotente: re-ejecutar no duplica filas. Cada corrida procesa solo
las licitaciones que aún no tienen adjudicaciones.
"""

from __future__ import annotations

import argparse
import asyncio

import structlog

logger = structlog.get_logger(__name__)


async def _contar_pendientes() -> int:
    from sqlalchemy import exists, select

    from app.db.session import AsyncSessionLocal
    from app.models.adjudicacion import Adjudicacion
    from app.models.licitacion import Licitacion

    async with AsyncSessionLocal() as session:
        subq = (
            select(Adjudicacion.licitacion_codigo)
            .where(Adjudicacion.licitacion_codigo == Licitacion.codigo)
            .exists()
        )
        stmt = select(
            select(Licitacion.codigo)
            .where(
                Licitacion.estado_codigo == 8,
                Licitacion.raw_payload.is_not(None),
                ~subq,
            )
            .subquery()
        )
        # COUNT(*)
        from sqlalchemy import func, select as sa_select
        count_stmt = sa_select(
            func.count()
        ).select_from(
            select(Licitacion.codigo)
            .where(
                Licitacion.estado_codigo == 8,
                Licitacion.raw_payload.is_not(None),
                ~subq,
            )
            .subquery()
        )
        result = (await session.execute(count_stmt)).scalar_one()
    return int(result)


async def _backfill(limit: int, dry_run: bool) -> None:
    from sqlalchemy import exists, select

    from app.db.session import AsyncSessionLocal, engine
    from app.models.adjudicacion import Adjudicacion
    from app.models.licitacion import Licitacion
    from app.schemas.chilecompra import LicitacionDetalleAPI
    from app.tasks.sync_detalle import _sync_adjudicaciones

    # Cada script tiene su propio event loop — dispose evita "Future attached to different loop"
    await engine.dispose()

    # 1. Licitaciones adjudicadas con raw_payload y sin adjudicaciones
    async with AsyncSessionLocal() as session:
        subq = (
            select(Adjudicacion.licitacion_codigo)
            .where(Adjudicacion.licitacion_codigo == Licitacion.codigo)
            .exists()
        )
        stmt = (
            select(Licitacion.codigo, Licitacion.raw_payload)
            .where(
                Licitacion.estado_codigo == 8,
                Licitacion.raw_payload.is_not(None),
                ~subq,
            )
            .order_by(Licitacion.fecha_publicacion.desc().nullslast())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()

    total = len(rows)
    if total == 0:
        print("Nada que procesar — la tabla adjudicaciones ya está al día.")
        return

    print(f"Procesando {total} licitaciones adjudicadas sin datos de adjudicación...")
    if dry_run:
        print("(Modo dry-run: no se escribe nada en BD)\n")

    ok = 0
    sin_adj = 0
    errores = 0

    for i, (codigo, raw_payload) in enumerate(rows, 1):
        # Re-parsear el JSON almacenado con los schemas actualizados
        try:
            detalle = LicitacionDetalleAPI.model_validate(raw_payload)
        except Exception as e:
            logger.warning("backfill_parse_error", codigo=codigo, error=str(e))
            print(f"  [{i}/{total}] {codigo} — ERROR al parsear: {e}")
            errores += 1
            continue

        if not detalle.Items or not detalle.Items.Listado:
            sin_adj += 1
            continue

        # Contar proveedores que se van a insertar
        proveedores = {
            item.Adjudicacion.RutProveedor
            for item in detalle.Items.Listado
            if item.Adjudicacion and item.Adjudicacion.RutProveedor
        }

        if not proveedores:
            sin_adj += 1
            continue

        if dry_run:
            print(f"  [{i}/{total}] {codigo} → {len(proveedores)} proveedor(es)")
            ok += 1
            continue

        try:
            async with AsyncSessionLocal() as session:
                await _sync_adjudicaciones(
                    session, codigo, detalle.Items.Listado, detalle.Fechas
                )
                await session.commit()
            ok += 1
            if i % 50 == 0 or i == total:
                logger.info("backfill_progress", procesadas=ok, total=total)
                print(f"  [{i}/{total}] {ok} OK · {sin_adj} sin adj · {errores} errores")
        except Exception as e:
            logger.error("backfill_error", codigo=codigo, error=str(e))
            print(f"  [{i}/{total}] {codigo} — ERROR: {e}")
            errores += 1

    print(
        f"\nResumen: {ok} procesadas · {sin_adj} sin adjudicaciones en items · {errores} errores"
    )
    if not dry_run and (ok + errores) < total:
        restantes = total - ok - errores
        print(f"Quedan ~{restantes} licitaciones. Volvé a ejecutar para el próximo lote.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill adjudicaciones desde raw_payload (sin llamadas a la API)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Máximo de licitaciones a procesar por corrida (default: 500)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra qué procesaría, sin escribir en BD",
    )
    args = parser.parse_args()

    asyncio.run(_backfill(limit=args.limit, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
