"""Tarea Celery: validación de ticket de ChileCompra recién registrado.

Reglas de oro que aplican:
- #2:  Ticket descifrado solo en memoria, nunca persistir en claro.
- #12: Sin PII en logs — nunca loggear el ticket.
- #29: Tarea idempotente — re-ejecutar no duplica efectos.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any
import uuid

import structlog

from app.celery_app import celery_app
from app.core.encryption import decrypt_ticket
from app.models.enums import TicketStatus

logger = structlog.get_logger()


@celery_app.task(  # type: ignore
    name="tasks.validate_ticket.validate_ticket_api",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def validate_ticket_api(self: Any, ticket_id: str) -> None:
    """Valida un ticket ChileCompra haciendo un ping mínimo a la API.

    Actualiza el status en BD: active si es válido, error si falla.
    Deja el ticket en pending si el error es transitorio (ej: timeout).
    """
    asyncio.run(_validate_async(ticket_id))


async def _validate_async(ticket_id_str: str) -> None:
    from app.db.session import AsyncSessionLocal
    from app.models.ticket import TicketApi
    from app.services.chilecompra.client import MercadoPublicoClient
    from app.services.chilecompra.enums import EstadoLicitacion
    from app.services.chilecompra.exceptions import (
        MercadoPublicoError,
        TicketInvalidoError,
    )

    ticket_id = uuid.UUID(ticket_id_str)

    async with AsyncSessionLocal() as db:
        ticket: TicketApi | None = await db.get(TicketApi, ticket_id)
        if ticket is None:
            logger.warning("validate_ticket_not_found", ticket_id=ticket_id_str)
            return

        try:
            ticket_plaintext = decrypt_ticket(ticket.ticket_cifrado)
        except Exception as exc:
            logger.error("validate_ticket_decrypt_error", ticket_id=ticket_id_str, error=str(exc))
            ticket.status = TicketStatus.error
            ticket.ultimo_error = "Error de descifrado — clave inválida"
            ticket.ultima_validacion_at = datetime.now(UTC)
            ticket.updated_at = datetime.now(UTC)
            await db.commit()
            return

        try:
            async with MercadoPublicoClient() as client:
                await client.listar_licitaciones_por_estado(
                    estado=EstadoLicitacion.ACTIVAS,
                    ticket=ticket_plaintext,
                    ticket_id=ticket.id,
                    empresa_id=ticket.empresa_id,
                )

            ticket.status = TicketStatus.active
            ticket.ultima_validacion_at = datetime.now(UTC)
            ticket.ultimo_error = None
            ticket.updated_at = datetime.now(UTC)
            logger.info("validate_ticket_activated", ticket_id=ticket_id_str)

        except TicketInvalidoError as exc:
            ticket.status = TicketStatus.error
            ticket.ultimo_error = str(exc)
            ticket.ultima_validacion_at = datetime.now(UTC)
            ticket.updated_at = datetime.now(UTC)
            logger.warning("validate_ticket_invalid", ticket_id=ticket_id_str, error=str(exc))

        except MercadoPublicoError as exc:
            # Error transitorio (timeout, 5xx): dejar en pending para reintento manual
            ticket.ultimo_error = f"Error al validar: {exc}"
            ticket.ultima_validacion_at = datetime.now(UTC)
            ticket.updated_at = datetime.now(UTC)
            logger.error("validate_ticket_transient_error", ticket_id=ticket_id_str, error=str(exc))

        except Exception as exc:
            ticket.ultimo_error = f"Error inesperado: {exc}"
            ticket.ultima_validacion_at = datetime.now(UTC)
            ticket.updated_at = datetime.now(UTC)
            logger.error("validate_ticket_unexpected", ticket_id=ticket_id_str, error=str(exc))

        finally:
            del ticket_plaintext

        await db.commit()
