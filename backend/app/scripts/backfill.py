"""Script de backfill histórico de licitaciones.

USO:
    python -m app.scripts.backfill --months 3 --dry-run
    python -m app.scripts.backfill --months 24

FUENTE DE DATOS:
    Usa la API de ChileCompra (endpoint /licitaciones.json?fecha=DDMMAAAA).
    Requiere un ticket activo en la BD.

NOTA SOBRE DATOS ABIERTOS:
    El portal datos-abiertos.chilecompra.cl no expone CSVs históricos masivos
    con descarga directa pública. El sitio sirve visualizaciones analíticas via
    API REST que requiere autenticación/contexto de sesión, y descargas por
    organismo específico (no dumps anuales). Esta limitación fue descubierta y
    documentada en la Retrospectiva Sprint 1. El backfill histórico se realiza
    por la API oficial con cuota de 10K req/día por ticket.

CUOTA:
    Regla de oro #16: bulk loads SOLO en horario nocturno (22:00-07:00 CLT).
    Regla de oro #18: máximo 5 req/s por ticket. Backoff exponencial ante 429.
    Regla de oro #29: idempotente — re-ejecutar no duplica registros (ON CONFLICT).

    Con 10.000 req/día y consulta por fecha (~1 req/fecha), se pueden cargar
    hasta 10.000 días = ~27 años de historia en un día de cuota.
    En la práctica cada fecha puede retornar hasta 1000 licitaciones.

EJECUCIÓN RECOMENDADA:
    - Nocturna (22:00-07:00 CLT) para no interferir con sincronización diurna.
    - Iniciar con --months 3 para validar el pipeline, luego --months 24 completo.
    - El script puede interrumpirse y retomarse (idempotencia garantizada).
"""

import argparse
import asyncio
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger()


# ============================================================
# Helpers
# ============================================================


def _hash_licitacion(codigo: str, nombre: str, estado_codigo: int | None) -> str:
    """SHA-256 del contenido básico — idéntico al de sync_chilecompra.py."""
    content = json.dumps(
        {"codigo": codigo, "nombre": nombre, "estado": estado_codigo},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def _fechas_a_procesar(meses: int) -> list[date]:
    """Genera lista de fechas desde hoy hacia atrás por N meses.

    Excluye fines de semana (Mercado Público publica principalmente en días hábiles,
    pero incluirlos igual para no perder publicaciones en fines de semana).
    """
    hoy = date.today()
    inicio = hoy - timedelta(days=meses * 30)
    fechas = []
    current = hoy - timedelta(days=1)  # Empezar desde ayer (hoy ya lo cubre sync)
    while current >= inicio:
        fechas.append(current)
        current -= timedelta(days=1)
    return fechas


# ============================================================
# Core async logic
# ============================================================


async def _get_ticket_activo(session: AsyncSession) -> tuple[str, str, str] | None:
    """Retorna (empresa_id, ticket_cifrado, ticket_id) del primer ticket activo.

    Regla de oro #12: no loggear el ticket en claro.
    """
    from app.models.enums import TicketStatus
    from app.models.ticket import TicketApi

    result = await session.execute(
        select(
            TicketApi.empresa_id,
            TicketApi.ticket_cifrado,
            TicketApi.id,
        )
        .where(TicketApi.status == TicketStatus.active)
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None
    empresa_id, ticket_cifrado, ticket_id = row
    return str(empresa_id), ticket_cifrado, str(ticket_id)


async def _upsert_licitacion(
    session: AsyncSession,
    codigo: str,
    nombre: str,
    estado_codigo: int | None,
    fecha_cierre: datetime | None,
) -> str:
    """Inserta o actualiza una licitación.

    Retorna: 'nueva' | 'actualizada' | 'sin_cambio'.
    """
    from datetime import datetime

    from app.models.enums import LicitacionEstado
    from app.models.licitacion import Licitacion
    from app.services.chilecompra.enums import EstadoLicitacion

    nuevo_hash = _hash_licitacion(codigo, nombre, estado_codigo)
    existing = await session.get(Licitacion, codigo)

    if existing is not None:
        if existing.hash_contenido == nuevo_hash:
            return "sin_cambio"
        existing.nombre = nombre
        estado_enum = EstadoLicitacion.from_codigo(estado_codigo or 5)
        existing.estado = LicitacionEstado(estado_enum.estado_interno)
        existing.estado_codigo = estado_codigo
        existing.fecha_cierre = fecha_cierre
        existing.hash_contenido = nuevo_hash
        existing.updated_at = datetime.now(UTC)
        return "actualizada"

    estado_enum = EstadoLicitacion.from_codigo(estado_codigo or 5)
    licitacion = Licitacion(
        codigo=codigo,
        nombre=nombre,
        estado=LicitacionEstado(estado_enum.estado_interno),
        estado_codigo=estado_codigo,
        fecha_cierre=fecha_cierre,
        hash_contenido=nuevo_hash,
    )
    session.add(licitacion)
    return "nueva"


async def _procesar_fecha(
    fecha: date,
    ticket_plaintext: str,
    ticket_id_uuid: uuid.UUID | None,
    empresa_id_uuid: uuid.UUID | None,
    dry_run: bool,
) -> dict[str, int]:
    """Descarga y persiste licitaciones de una fecha específica.

    Regla de oro #18: rate limit maneja el cliente.
    Regla de oro #29: upsert idempotente.
    """

    from app.db.session import AsyncSessionLocal
    from app.services.chilecompra.client import MercadoPublicoClient
    from app.services.chilecompra.exceptions import MercadoPublicoError

    stats: dict[str, int] = {
        "nuevas": 0,
        "actualizadas": 0,
        "sin_cambio": 0,
        "errores": 0,
    }

    try:
        async with MercadoPublicoClient() as client:
            response = await client.listar_licitaciones_por_fecha(
                fecha=fecha,
                ticket=ticket_plaintext,
                ticket_id=ticket_id_uuid,
                empresa_id=empresa_id_uuid,
            )

        if not response.Listado:
            return stats

        if dry_run:
            stats["nuevas"] = len(response.Listado)
            return stats

        async with AsyncSessionLocal() as session:
            for item in response.Listado:
                try:
                    resultado = await _upsert_licitacion(
                        session=session,
                        codigo=item.CodigoExterno,
                        nombre=item.Nombre,
                        estado_codigo=item.CodigoEstado,
                        fecha_cierre=item.FechaCierre,
                    )
                    stats[resultado] += 1
                except Exception as e:
                    logger.error(
                        "backfill_licitacion_error",
                        codigo=item.CodigoExterno,
                        error=str(e),
                    )
                    stats["errores"] += 1

            await session.commit()

    except MercadoPublicoError as e:
        logger.warning(
            "backfill_fecha_error",
            fecha=str(fecha),
            error=str(e),
            status_code=getattr(e, "status_code", None),
        )
        stats["errores"] += 1

    return stats


async def run_backfill(meses: int, dry_run: bool) -> None:
    """Orquesta el backfill completo.

    Args:
        meses: Cantidad de meses hacia atrás a cubrir.
        dry_run: Si True, solo cuenta sin persistir.
    """
    import uuid

    from app.core.encryption import decrypt_ticket
    from app.db.session import AsyncSessionLocal

    logger.info("backfill_start", meses=meses, dry_run=dry_run)

    # Generar lista de fechas
    fechas = _fechas_a_procesar(meses)
    total_fechas = len(fechas)

    logger.info("backfill_fechas_a_procesar", total=total_fechas, dry_run=dry_run)

    if dry_run:
        print(f"DRY RUN — Fechas a procesar: {total_fechas}")
        print(f"  Desde: {fechas[-1]} hasta: {fechas[0]}")
        print(f"  Cuota estimada: {total_fechas} requests (1 por fecha)")
        print(
            "  NOTA: Datos Abiertos de ChileCompra no tiene CSVs de descarga directa.\n"
            "  El backfill usa la API oficial (cuota 10K req/día por ticket).\n"
            "  Ejecutar en horario nocturno (22:00-07:00 CLT) — regla de oro #17."
        )
        return

    # Obtener ticket activo (no se necesita en dry-run)
    async with AsyncSessionLocal() as session:
        ticket_info = await _get_ticket_activo(session)

    if ticket_info is None:
        logger.error("backfill_no_ticket_activo")
        print(
            "ERROR: No hay tickets activos en la BD.\n"
            "Cargá un ticket via el panel admin o el script create_user."
        )
        sys.exit(1)

    empresa_id_str, ticket_cifrado, ticket_id_str = ticket_info

    # Descifrar solo en memoria — NUNCA loggear (regla de oro #2)
    try:
        ticket_plaintext = decrypt_ticket(ticket_cifrado)
    except Exception as e:
        logger.error("backfill_decrypt_failed", error=str(e))
        print(f"ERROR: No se pudo descifrar el ticket: {e}")
        sys.exit(1)

    try:
        empresa_id_uuid: uuid.UUID | None = uuid.UUID(empresa_id_str)
        ticket_id_uuid: uuid.UUID | None = uuid.UUID(ticket_id_str)
    except ValueError:
        empresa_id_uuid = None
        ticket_id_uuid = None

    # Acumuladores de estadísticas
    total: dict[str, int] = {
        "nuevas": 0,
        "actualizadas": 0,
        "sin_cambio": 0,
        "errores": 0,
    }
    batch_size = 100  # Loggear progreso cada N fechas

    for i, fecha in enumerate(fechas, 1):
        stats = await _procesar_fecha(
            fecha=fecha,
            ticket_plaintext=ticket_plaintext,
            ticket_id_uuid=ticket_id_uuid,
            empresa_id_uuid=empresa_id_uuid,
            dry_run=False,
        )
        for k, v in stats.items():
            total[k] = total.get(k, 0) + v

        if i % batch_size == 0:
            logger.info(
                "backfill_progreso",
                procesadas=i,
                total=total_fechas,
                **total,
            )
            # Mostrar en stdout para visibilidad en CLI
            acum = total["nuevas"] + total["actualizadas"]
            print(
                f"  {i}/{total_fechas} fechas | {acum:,} licitaciones cargadas | "
                f"errores: {total['errores']}"
            )

    # Limpiar referencia al ticket
    del ticket_plaintext

    logger.info("backfill_done", **total)
    print(
        f"\n✅ Backfill completado:\n"
        f"   Nuevas:      {total['nuevas']:>8,}\n"
        f"   Actualizadas:{total['actualizadas']:>8,}\n"
        f"   Sin cambio:  {total['sin_cambio']:>8,}\n"
        f"   Errores:     {total['errores']:>8,}\n"
    )


# ============================================================
# Tests unitarios básicos (ejecutar con pytest o directamente)
# ============================================================


def test_hash_licitacion_idempotente() -> None:
    """El hash del mismo input siempre es igual (para idempotencia)."""
    h1 = _hash_licitacion("1000-1-L126", "Servicio de limpieza", 5)
    h2 = _hash_licitacion("1000-1-L126", "Servicio de limpieza", 5)
    assert h1 == h2, "Hash debe ser determinista"


def test_hash_licitacion_distingue_cambios() -> None:
    """Cambios en cualquier campo producen hash diferente."""
    h1 = _hash_licitacion("1000-1-L126", "Servicio de limpieza", 5)
    h2 = _hash_licitacion("1000-1-L126", "Servicio de limpieza", 8)  # estado cambió
    assert h1 != h2, "Hash debe cambiar si cambia el estado"


def test_fechas_a_procesar_cantidad() -> None:
    """Genera la cantidad correcta de fechas."""
    fechas = _fechas_a_procesar(1)
    assert len(fechas) >= 28, "Un mes debe tener al menos 28 fechas"
    assert len(fechas) <= 32, "Un mes no debe tener más de 32 fechas"


def test_fechas_a_procesar_orden() -> None:
    """Las fechas están en orden descendente (más reciente primero)."""
    fechas = _fechas_a_procesar(1)
    assert fechas[0] > fechas[-1], "Primera fecha debe ser más reciente que la última"


# ============================================================
# Entrypoint CLI
# ============================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill histórico de licitaciones desde la API de ChileCompra.\n\n"
            "IMPORTANTE: Ejecutar en horario nocturno (22:00-07:00 CLT).\n"
            "Cuota: 10.000 req/día por ticket. ~1 req por fecha consultada."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--months",
        type=int,
        default=3,
        help="Meses hacia atrás a procesar (default: 3, máximo recomendado: 24)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Estima el trabajo sin ejecutar (no consume cuota ni persiste datos)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Ejecuta los tests unitarios del script",
    )

    args = parser.parse_args()

    if args.test:
        print("Ejecutando tests del script...")
        test_hash_licitacion_idempotente()
        test_hash_licitacion_distingue_cambios()
        test_fechas_a_procesar_cantidad()
        test_fechas_a_procesar_orden()
        print("✅ Todos los tests pasaron")
        return

    if args.months > 24:
        print(
            f"WARNING: --months {args.months} es mayor al recomendado (24).\n"
            "Esto puede consumir mucha cuota. Considerá ejecutar en múltiples noches."
        )

    print(f"{'DRY RUN — ' if args.dry_run else ''}Backfill histórico: {args.months} meses")
    if not args.dry_run:
        print(
            "⚠  Regla de oro #17: ejecutar solo en horario nocturno (22:00-07:00 CLT)\n"
            "⚠  Regla de oro #18: rate limit interno activo (5 req/s)\n"
        )

    asyncio.run(run_backfill(meses=args.months, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
