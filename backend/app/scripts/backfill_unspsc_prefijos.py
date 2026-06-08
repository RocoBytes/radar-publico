"""Backfill de unspsc_prefijos para licitaciones históricas.

Pobla la columna `unspsc_prefijos text[]` en todas las licitaciones que tienen
ítems cargados pero cuya columna aún es NULL (no fue procesada por el trigger
porque existían antes de la migración 20260607_1000).

Estrategia:
  - Una sola query bulk UPDATE en SQL puro — más eficiente que iterar en Python.
  - Si la tabla tiene muchas filas, usar --batch-size para procesar por lotes y
    evitar lockear demasiadas filas a la vez.

USO:
    python -m app.scripts.backfill_unspsc_prefijos
    python -m app.scripts.backfill_unspsc_prefijos --batch-size 5000 --dry-run

Reglas de oro:
  - #19: Sin N+1 — se usa una sola subquery correlacionada a nivel de SQL.
  - #29: Idempotente — WHERE unspsc_prefijos IS NULL limita el efecto a filas
         aún no procesadas; re-ejecutar es seguro.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.engine import CursorResult
import structlog

logger = structlog.get_logger()

_BULK_SQL = """
UPDATE licitaciones
SET unspsc_prefijos = (
  SELECT array_agg(DISTINCT prefijo)
  FROM licitacion_items li
  CROSS JOIN LATERAL (
    SELECT SUBSTRING(li.unspsc_codigo, 1, n) AS prefijo
    FROM generate_series(2, 8, 2) n
    WHERE LENGTH(li.unspsc_codigo) >= n
  ) AS p
  WHERE li.licitacion_codigo = licitaciones.codigo
    AND li.unspsc_codigo IS NOT NULL
)
WHERE unspsc_prefijos IS NULL
  AND EXISTS (
    SELECT 1
    FROM licitacion_items li2
    WHERE li2.licitacion_codigo = licitaciones.codigo
      AND li2.unspsc_codigo IS NOT NULL
  )
"""

_BATCH_SQL = """
UPDATE licitaciones
SET unspsc_prefijos = (
  SELECT array_agg(DISTINCT prefijo)
  FROM licitacion_items li
  CROSS JOIN LATERAL (
    SELECT SUBSTRING(li.unspsc_codigo, 1, n) AS prefijo
    FROM generate_series(2, 8, 2) n
    WHERE LENGTH(li.unspsc_codigo) >= n
  ) AS p
  WHERE li.licitacion_codigo = licitaciones.codigo
    AND li.unspsc_codigo IS NOT NULL
)
WHERE codigo IN (
  SELECT codigo FROM licitaciones
  WHERE unspsc_prefijos IS NULL
    AND EXISTS (
      SELECT 1 FROM licitacion_items li3
      WHERE li3.licitacion_codigo = licitaciones.codigo
        AND li3.unspsc_codigo IS NOT NULL
    )
  ORDER BY codigo
  LIMIT :batch_size
)
"""

_COUNT_SQL = """
SELECT COUNT(*) FROM licitaciones
WHERE unspsc_prefijos IS NULL
  AND EXISTS (
    SELECT 1 FROM licitacion_items li
    WHERE li.licitacion_codigo = licitaciones.codigo
      AND li.unspsc_codigo IS NOT NULL
  )
"""


async def _run(batch_size: int, dry_run: bool) -> None:
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        total_row = await session.execute(text(_COUNT_SQL))
        pendientes = total_row.scalar_one()

    if pendientes == 0:
        logger.info("backfill_unspsc_prefijos_nada_pendiente")
        print("Nada que backfillear — unspsc_prefijos ya está poblado en todas las filas.")
        return

    print(f"Licitaciones pendientes: {pendientes}")

    if dry_run:
        print("[DRY RUN] Sin cambios aplicados.")
        return

    if batch_size == 0:
        # Una sola query — simple y eficiente para tablas pequeñas/medianas
        async with AsyncSessionLocal() as session:
            result = cast(CursorResult[Any], await session.execute(text(_BULK_SQL)))
            await session.commit()
        logger.info("backfill_unspsc_prefijos_ok", actualizadas=result.rowcount)
        print(f"Backfill completado: {result.rowcount} licitaciones actualizadas.")
        return

    # Modo batched — procesar de a `batch_size` filas para no lockear demasiado
    total_actualizadas = 0
    batch_num = 0
    while True:
        async with AsyncSessionLocal() as session:
            result = cast(
                CursorResult[Any],
                await session.execute(text(_BATCH_SQL), {"batch_size": batch_size}),
            )
            await session.commit()

        rows = result.rowcount
        if rows == 0:
            break
        total_actualizadas += rows
        batch_num += 1
        logger.info(
            "backfill_unspsc_prefijos_batch",
            batch=batch_num,
            actualizadas_batch=rows,
            total_acumulado=total_actualizadas,
        )
        print(f"  Batch {batch_num}: {rows} filas actualizadas (total: {total_actualizadas})")

    print(
        f"Backfill completado: {total_actualizadas} licitaciones"
        f" actualizadas en {batch_num} batches."
    )
    logger.info(
        "backfill_unspsc_prefijos_fin",
        total_actualizadas=total_actualizadas,
        batches=batch_num,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill de unspsc_prefijos para licitaciones históricas."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=0,
        help="Filas por lote (0 = una sola query, recomendado para <100K filas).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo reporta cuántas filas se actualizarían, sin modificar nada.",
    )
    args = parser.parse_args()

    try:
        asyncio.run(_run(batch_size=args.batch_size, dry_run=args.dry_run))
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
