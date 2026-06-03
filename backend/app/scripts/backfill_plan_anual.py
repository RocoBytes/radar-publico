"""Script de backfill histórico del Plan Anual de Compras (PAC).

USO:
    python -m app.scripts.backfill_plan_anual --ano 2025
    python -m app.scripts.backfill_plan_anual --ano 2024 --force

CUOTA:
    Regla de oro #17: bulk loads SOLO en horario nocturno (22:00-07:00 CLT).
    Regla de oro #18: máximo 5 req/s. Backoff exponencial ante 429/5xx.
    Regla de oro #29: idempotente — upsert no duplica filas.
    Regla de oro #2:  ticket descifrado solo en memoria, nunca loggear.

EJECUCIÓN RECOMENDADA:
    - Nocturna (22:00-07:00 CLT) para no interferir con la cuota diurna.
    - Un año por corrida. Cada organismo puede tener cientos de líneas.
    - Puede interrumpirse y retomarse (idempotencia garantizada por upsert).
"""

import argparse
import asyncio
from datetime import UTC, datetime
import sys
from zoneinfo import ZoneInfo

import structlog

logger = structlog.get_logger()

_CLT = ZoneInfo("America/Santiago")

# Rango de la ventana nocturna (hora local CLT)
_HORA_INICIO_NOCTURNO = 22  # 22:00
_HORA_FIN_NOCTURNO = 7  # 07:00 (del día siguiente)


def _es_horario_nocturno() -> bool:
    """Verifica si la hora actual está dentro de la ventana nocturna CLT.

    La ventana es 22:00-07:00, cruza la medianoche.
    Regla de oro #17.
    """
    ahora_clt = datetime.now(_CLT)
    hora = ahora_clt.hour
    return hora >= _HORA_INICIO_NOCTURNO or hora < _HORA_FIN_NOCTURNO


async def _get_tickets_activos() -> list[tuple[str, str, str]]:
    """Retorna lista de (empresa_id, ticket_cifrado, ticket_id) para tickets activos.

    Regla de oro #12: no se loggea el ticket.
    """
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.enums import TicketStatus
    from app.models.ticket import TicketApi

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                TicketApi.empresa_id,
                TicketApi.ticket_cifrado,
                TicketApi.id,
            ).where(TicketApi.status == TicketStatus.active)
        )
        rows = result.all()

    return [(str(e), tc, str(tid)) for e, tc, tid in rows]


async def run_backfill(ano: int, force: bool) -> None:
    """Orquesta el backfill del plan anual para un año completo.

    Para cada empresa con ticket activo descarga todas las páginas del PAC
    del año indicado y las persiste con upsert idempotente.

    Args:
        ano: Año del plan anual a cargar.
        force: Si True, omite el check de ventana nocturna.
    """
    # Guard de ventana nocturna — regla de oro #17
    if not _es_horario_nocturno() and not force:
        ahora_clt = datetime.now(_CLT).strftime("%H:%M CLT")
        print(
            f"\nAVISO: Son las {ahora_clt}, fuera de la ventana nocturna recomendada "
            f"(22:00-07:00 CLT).\n"
            "Ejecutar cargas masivas en horario diurno puede interferir con la cuota\n"
            "de sincronización en tiempo real (regla de oro #17).\n\n"
            "Opciones:\n"
            "  Esperá hasta las 22:00 CLT, o\n"
            "  Ejecutá con --force para omitir este check."
        )
        sys.exit(1)

    from app.db.session import engine

    # Disponer el pool para evitar conflictos de event loop en scripts
    await engine.dispose()

    tickets = await _get_tickets_activos()

    if not tickets:
        logger.error("backfill_plan_anual_no_tickets")
        print(
            "ERROR: No hay tickets activos en la BD.\n"
            "Cargá un ticket via el panel admin antes de ejecutar el backfill."
        )
        sys.exit(1)

    logger.info(
        "backfill_plan_anual_start",
        ano=ano,
        empresas=len(tickets),
    )
    print(
        f"\nBackfill Plan Anual {ano}\n"
        f"Empresas con ticket activo: {len(tickets)}\n"
        "Regla de oro #18: rate limit activo (5 req/s)\n"
        "Regla de oro #29: upsert idempotente — puede interrumpirse y retomarse\n"
    )

    # Importar la lógica de sincronización de la tarea Celery para reutilizarla
    # en vez de duplicarla. El script llama la función async directamente.
    from app.core.encryption import decrypt_ticket
    from app.tasks.sync_plan_anual import _sync_plan_empresa

    total: dict[str, int] = {"upserted": 0, "paginas": 0, "errores": 0}
    lineas_desde_ultimo_log = 0

    for i, (empresa_id, ticket_cifrado, ticket_id) in enumerate(tickets, 1):
        # Verificar que el ticket se pueda descifrar antes de empezar
        try:
            _prueba = decrypt_ticket(ticket_cifrado)
            del _prueba
        except Exception as e:
            logger.error(
                "backfill_plan_anual_ticket_invalido",
                empresa_id=empresa_id,
                error=str(e),
            )
            print(f"  Empresa {i}/{len(tickets)}: ticket no válido, saltando.")
            continue

        logger.info(
            "backfill_plan_anual_empresa_inicio",
            empresa_id=empresa_id,
            ano=ano,
            empresa_num=i,
            empresa_total=len(tickets),
        )

        stats = await _sync_plan_empresa(
            empresa_id=empresa_id,
            ticket_cifrado=ticket_cifrado,
            ticket_id=ticket_id,
            anos=[ano],
        )

        for k, v in stats.items():
            total[k] = total.get(k, 0) + v

        lineas_desde_ultimo_log += stats["upserted"]

        logger.info(
            "backfill_plan_anual_empresa_fin",
            empresa_id=empresa_id,
            ano=ano,
            **stats,
        )
        print(
            f"  Empresa {i}/{len(tickets)}: "
            f"{stats['upserted']:,} líneas | "
            f"{stats['paginas']} páginas | "
            f"errores: {stats['errores']}"
        )

        # Log de progreso cada 100 líneas (puede cruzar varias empresas)
        if lineas_desde_ultimo_log >= 100:
            logger.info(
                "backfill_plan_anual_progreso",
                ano=ano,
                empresa_actual=i,
                empresa_total=len(tickets),
                acumulado_upserted=total["upserted"],
            )
            lineas_desde_ultimo_log = 0

        # Pequeña pausa entre empresas para no saturar la BD
        await asyncio.sleep(0.5)

    logger.info("backfill_plan_anual_done", ano=ano, **total)
    print(
        f"\nBackfill completado — Plan Anual {ano}:\n"
        f"   Lineas upserted: {total['upserted']:>8,}\n"
        f"   Paginas leidas:  {total['paginas']:>8,}\n"
        f"   Errores:         {total['errores']:>8,}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill historico del Plan Anual de Compras de ChileCompra.\n\n"
            "IMPORTANTE: Ejecutar en horario nocturno (22:00-07:00 CLT).\n"
            "Regla de oro #17 — bulk loads no deben interferir con la cuota diurna."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ano",
        type=int,
        required=True,
        help="Ano del plan anual a cargar (ej: 2024, 2025)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Omitir el check de ventana nocturna (usar con precaucion)",
    )

    args = parser.parse_args()

    ano_actual = datetime.now(UTC).year
    if args.ano < 2010 or args.ano > ano_actual + 2:
        print(f"ERROR: Año {args.ano} fuera del rango razonable " f"(2010-{ano_actual + 2}).")
        sys.exit(1)

    print(f"Backfill Plan Anual de Compras — año {args.ano}")
    if not args.force:
        print("Verificando ventana nocturna CLT...\n" "Usá --force para omitir el check.")

    asyncio.run(run_backfill(ano=args.ano, force=args.force))


if __name__ == "__main__":
    main()
