"""Tarea Celery: sincronización diaria de licitaciones desde ChileCompra.

Reglas de oro que aplican:
- #2:  Tickets descifrados solo en memoria, nunca persistir en claro.
- #12: Sin PII en logs — nunca loggear el ticket.
- #29: Tarea idempotente — re-ejecutar no duplica registros.
- #18: Rate limit interno de 5 req/s (lo maneja el cliente).
"""

import asyncio
from datetime import UTC, datetime
import hashlib
import json
from typing import Any

import structlog

from app.celery_app import celery_app
from app.core.encryption import decrypt_ticket
from app.models.enums import LicitacionEstado, TicketStatus
from app.services.chilecompra.client import MercadoPublicoClient
from app.services.chilecompra.enums import EstadoLicitacion
from app.services.chilecompra.exceptions import (
    MercadoPublicoError,
    TicketInvalidoError,
)

logger = structlog.get_logger()


def _hash_licitacion(codigo: str, nombre: str, estado_codigo: int | None) -> str:
    """SHA-256 del contenido básico para detectar cambios sin comparar campo a campo."""
    content = json.dumps(
        {"codigo": codigo, "nombre": nombre, "estado": estado_codigo},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(content.encode()).hexdigest()


async def _sync_empresa(
    empresa_id: str,
    ticket_cifrado: str,
    ticket_id: str,
    ticket_ultimos_4: str,
) -> dict[str, int]:
    """Sincroniza las licitaciones activas para una empresa.

    Returns:
        Dict con contadores: nuevas, actualizadas, sin_cambio, errores.
    """
    import uuid

    from app.db.session import AsyncSessionLocal
    from app.models.licitacion import Licitacion

    stats = {"nuevas": 0, "sin_cambio": 0, "errores": 0}

    # Descifrar ticket solo en memoria — NUNCA loggear ni persistir
    try:
        ticket_plaintext = decrypt_ticket(ticket_cifrado)
    except Exception as e:
        logger.error(
            "ticket_decrypt_failed",
            empresa_id=empresa_id,
            error=str(e),
        )
        stats["errores"] += 1
        return stats

    try:
        async with MercadoPublicoClient() as client:
            response = await client.listar_licitaciones_por_estado(
                estado=EstadoLicitacion.ACTIVAS,
                ticket=ticket_plaintext,
                ticket_id=uuid.UUID(ticket_id) if ticket_id else None,
                empresa_id=uuid.UUID(empresa_id),
            )

        logger.info(
            "chilecompra_listado_ok",
            empresa_id=empresa_id,
            cantidad=response.Cantidad,
        )

        async with AsyncSessionLocal() as session:
            for item in response.Listado:
                try:
                    # Buscar si ya existe (idempotencia — regla de oro #29)
                    existing = await session.get(Licitacion, item.CodigoExterno)
                    nuevo_hash = _hash_licitacion(
                        item.CodigoExterno, item.Nombre, item.CodigoEstado
                    )

                    if existing is not None:
                        if existing.hash_contenido == nuevo_hash:
                            stats["sin_cambio"] += 1
                            continue
                        # Solo actualizar si cambió algo
                        existing.nombre = item.Nombre
                        existing.estado = EstadoLicitacion.from_codigo(
                            item.CodigoEstado or 5
                        ).name.lower()  # type: ignore[assignment]
                        existing.estado_codigo = item.CodigoEstado
                        existing.fecha_cierre = item.FechaCierre
                        existing.hash_contenido = nuevo_hash
                        existing.updated_at = datetime.now(UTC)
                    else:
                        # Nueva licitación — solo info básica del listado
                        estado_enum = EstadoLicitacion.from_codigo(
                            item.CodigoEstado or 5
                        )
                        licitacion = Licitacion(
                            codigo=item.CodigoExterno,
                            nombre=item.Nombre,
                            estado=LicitacionEstado(estado_enum.estado_interno),
                            estado_codigo=item.CodigoEstado,
                            fecha_cierre=item.FechaCierre,
                            hash_contenido=nuevo_hash,
                            # detalle_sincronizado_at NULL — sync completo pendiente
                        )
                        session.add(licitacion)
                        stats["nuevas"] += 1

                except Exception as e:
                    logger.error(
                        "licitacion_persist_error",
                        codigo=item.CodigoExterno,
                        error=str(e),
                    )
                    stats["errores"] += 1

            await session.commit()

    except TicketInvalidoError:
        # Marcar el ticket como error en BD
        logger.warning(
            "ticket_invalido",
            empresa_id=empresa_id,
            ultimos_4=ticket_ultimos_4,
        )
        async with AsyncSessionLocal() as session:
            from sqlalchemy import update

            from app.models.ticket import TicketApi

            await session.execute(
                update(TicketApi)
                .where(TicketApi.empresa_id == uuid.UUID(empresa_id))
                .values(
                    status=TicketStatus.error,
                    ultimo_error="Ticket inválido o expirado",
                    ultima_validacion_at=datetime.now(UTC),
                )
            )
            await session.commit()
        stats["errores"] += 1

    except MercadoPublicoError as e:
        logger.error(
            "chilecompra_api_error",
            empresa_id=empresa_id,
            error=str(e),
            status_code=e.status_code,
        )
        stats["errores"] += 1

    finally:
        # Limpiar la referencia al ticket en texto claro
        del ticket_plaintext

    return stats


@celery_app.task(  # type: ignore[misc]
    name="tasks.sync_chilecompra.sync_listado_diario",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutos entre reintentos
    acks_late=True,
)
def sync_listado_diario(self: Any) -> dict[str, object]:  # Task sin stubs
    """Sincroniza las licitaciones activas de hoy para TODAS las empresas.

    Regla de oro #29: idempotente — re-ejecutar no duplica registros.
    Regla de oro #18: si un ticket falla, continúa con los demás.
    Regla de oro #2:  ticket descifrado solo en memoria.
    """
    logger.info("sync_listado_diario_start")

    async def _run() -> dict[str, object]:
        from sqlalchemy import select

        from app.db.session import AsyncSessionLocal
        from app.models.ticket import TicketApi

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(
                    TicketApi.empresa_id,
                    TicketApi.ticket_cifrado,
                    TicketApi.id,
                    TicketApi.ticket_ultimos_4,
                ).where(TicketApi.status == TicketStatus.active)
            )
            tickets = result.all()

        if not tickets:
            logger.info("sync_listado_diario_no_tickets")
            return {"empresas": 0, "total": {}}

        total: dict[str, int] = {"nuevas": 0, "sin_cambio": 0, "errores": 0}
        for empresa_id, ticket_cifrado, ticket_id, ultimos_4 in tickets:
            stats = await _sync_empresa(
                empresa_id=str(empresa_id),
                ticket_cifrado=ticket_cifrado,
                ticket_id=str(ticket_id),
                ticket_ultimos_4=ultimos_4,
            )
            for k, v in stats.items():
                total[k] = total.get(k, 0) + v

        logger.info(
            "sync_listado_diario_done",
            empresas=len(tickets),
            **total,
        )
        return {"empresas": len(tickets), "total": total}

    return asyncio.run(_run())
