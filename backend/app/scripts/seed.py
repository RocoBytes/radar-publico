"""Script de inicialización: admin + catálogos geográficos y UNSPSC.

Uso:
    docker compose exec api python -m app.scripts.seed --all
    docker compose exec api python -m app.scripts.seed --admin
    docker compose exec api python -m app.scripts.seed --catalogos

Todos los comandos son idempotentes — re-ejecutar no duplica datos.

Nota UNSPSC: el CSV incluido es una muestra de segmentos principales.
Para el catálogo completo (~70k filas), reemplazar:
    backend/app/scripts/seeds/unspsc_v14_es.csv
con el archivo oficial de ChileCompra y volver a ejecutar --catalogos.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
import sys

import structlog

logger = structlog.get_logger(__name__)

_SEEDS_DIR = Path(__file__).parent / "seeds"


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


async def _seed_admin() -> None:
    """Crea el usuario admin si no existe.

    Usa ADMIN_EMAIL y ADMIN_PASSWORD de settings. Si el email está vacío,
    no crea nada y avisa. Si el password está vacío, genera uno y lo imprime
    una sola vez.
    """
    from sqlalchemy import select

    from app.config import settings
    from app.core.security import generate_temporary_password, hash_password
    from app.db.session import AsyncSessionLocal
    from app.models.enums import UserRole, UserStatus
    from app.models.usuario import Usuario

    email = settings.admin_email.strip()
    if not email:
        logger.warning(
            "seed_admin_skip",
            razon="ADMIN_EMAIL no configurado en .env",
        )
        print(
            "  [SKIP] ADMIN_EMAIL vacío — define ADMIN_EMAIL en .env para crear admin.",
            file=sys.stderr,
        )
        return

    async with AsyncSessionLocal() as session:
        existente = (
            await session.execute(select(Usuario).where(Usuario.email == email))
        ).scalar_one_or_none()

        if existente is not None:
            logger.info("seed_admin_ya_existe", email_suffix=email[-4:])
            print(f"  [OK] Admin ya existe ({email}).")
            return

        password = settings.admin_password.strip()
        generado = False
        if not password:
            password = generate_temporary_password()
            generado = True

        usuario = Usuario(
            email=email,
            password_hash=hash_password(password),
            rol=UserRole.admin,
            status=UserStatus.active,
            must_change_password=generado,
        )
        session.add(usuario)
        await session.commit()

    logger.info("seed_admin_creado", email_suffix=email[-4:])

    print()
    print("=" * 60)
    print("  ADMIN CREADO")
    print("=" * 60)
    print(f"  Email    : {email}")
    print(f"  Password : {password}")
    if generado:
        print()
        print("  ⚠  Password generado — cámbialo al primer ingreso.")
    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------


async def _seed_regiones() -> int:
    """Carga las 16 regiones de Chile. Retorna cantidad insertada."""
    csv_path = _SEEDS_DIR / "regiones_chile.csv"
    if not csv_path.exists():
        logger.warning("seed_regiones_csv_no_encontrado", path=str(csv_path))
        return 0

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.db.session import AsyncSessionLocal
    from app.models.catalogos import Region

    rows: list[dict[str, object]] = []
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "codigo": row["codigo"],
                    "nombre": row["nombre"],
                    "nombre_corto": row.get("nombre_corto") or None,
                    "orden": int(row["orden"]) if row.get("orden") else None,
                }
            )

    if not rows:
        return 0

    async with AsyncSessionLocal() as session:
        stmt = pg_insert(Region).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["codigo"])
        result = await session.execute(stmt)
        await session.commit()

    insertadas = result.rowcount if result.rowcount is not None else 0
    logger.info("seed_regiones_ok", insertadas=insertadas, total=len(rows))
    return insertadas


async def _seed_comunas() -> int:
    """Carga las comunas de Chile. Retorna cantidad insertada."""
    csv_path = _SEEDS_DIR / "comunas_chile.csv"
    if not csv_path.exists():
        logger.warning("seed_comunas_csv_no_encontrado", path=str(csv_path))
        return 0

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.db.session import AsyncSessionLocal
    from app.models.catalogos import Comuna

    rows: list[dict[str, object]] = []
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "codigo": row["codigo"],
                    "nombre": row["nombre"],
                    "region_codigo": row["region_codigo"],
                }
            )

    if not rows:
        return 0

    async with AsyncSessionLocal() as session:
        stmt = pg_insert(Comuna).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["codigo"])
        result = await session.execute(stmt)
        await session.commit()

    insertadas = result.rowcount if result.rowcount is not None else 0
    logger.info("seed_comunas_ok", insertadas=insertadas, total=len(rows))
    return insertadas


async def _seed_unspsc() -> int:
    """Carga el catálogo UNSPSC desde CSV. Retorna cantidad insertada.

    Orden de inserción importa: primero los padres (nivel 1), luego hijos.
    El CSV ya debe estar ordenado por nivel ascendente.
    """
    csv_path = _SEEDS_DIR / "unspsc_v14_es.csv"
    if not csv_path.exists():
        logger.warning("seed_unspsc_csv_no_encontrado", path=str(csv_path))
        print(
            f"  [SKIP] {csv_path} no encontrado. "
            "Proveer CSV de UNSPSC v14 para cargar el catálogo completo.",
            file=sys.stderr,
        )
        return 0

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.db.session import AsyncSessionLocal
    from app.models.catalogos import Unspsc

    # Leer y agrupar por nivel para respetar FK parent_codigo
    by_nivel: dict[int, list[dict[str, object]]] = {}
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            nivel = int(row["nivel"])
            entry: dict[str, object] = {
                "codigo": row["codigo"],
                "nombre_es": row["nombre_es"],
                "descripcion_es": row.get("descripcion_es") or None,
                "nivel": nivel,
                "segmento": row.get("segmento") or None,
                "familia": row.get("familia") or None,
                "clase": row.get("clase") or None,
                "parent_codigo": row.get("parent_codigo") or None,
                "activo": True,
            }
            by_nivel.setdefault(nivel, []).append(entry)

    total_insertados = 0
    async with AsyncSessionLocal() as session:
        for nivel in sorted(by_nivel.keys()):
            rows = by_nivel[nivel]
            stmt = pg_insert(Unspsc).values(rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=["codigo"])
            result = await session.execute(stmt)
            insertados = result.rowcount if result.rowcount is not None else 0
            total_insertados += insertados
            logger.debug(
                "seed_unspsc_nivel_ok",
                nivel=nivel,
                insertados=insertados,
                total_nivel=len(rows),
            )
        await session.commit()

    logger.info("seed_unspsc_ok", insertados=total_insertados)
    return total_insertados


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------


async def _main(args: argparse.Namespace) -> None:
    hacer_admin = args.admin or args.all
    hacer_catalogos = args.catalogos or args.all

    if not hacer_admin and not hacer_catalogos:
        print("Nada que hacer. Usá --admin, --catalogos o --all.", file=sys.stderr)
        sys.exit(1)

    if hacer_admin:
        print("→ Creando admin...")
        await _seed_admin()

    if hacer_catalogos:
        print("→ Cargando regiones...")
        n = await _seed_regiones()
        print(f"  {n} regiones insertadas.")

        print("→ Cargando comunas...")
        n = await _seed_comunas()
        print(f"  {n} comunas insertadas.")

        print("→ Cargando UNSPSC...")
        n = await _seed_unspsc()
        print(f"  {n} códigos UNSPSC insertados.")

    print("\nSeed completado.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inicializa la base de datos con datos de referencia"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ejecutar admin + catálogos",
    )
    parser.add_argument(
        "--admin",
        action="store_true",
        help="Crear usuario admin desde .env",
    )
    parser.add_argument(
        "--catalogos",
        action="store_true",
        help="Cargar regiones, comunas y UNSPSC",
    )
    args = parser.parse_args()
    asyncio.run(_main(args))


if __name__ == "__main__":
    main()
