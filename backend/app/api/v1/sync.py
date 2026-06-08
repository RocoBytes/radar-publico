"""Endpoint para disparar sincronización manual de licitaciones.

Solo encola la tarea — el resultado llega en background via Celery.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser  # noqa: TCH001
from app.celery_app import celery_app

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncTriggerResponse(BaseModel):
    status: str
    message: str
    enqueued_at: datetime


@router.post("/licitaciones", response_model=SyncTriggerResponse)
async def trigger_sync_licitaciones(current_user: CurrentUser) -> SyncTriggerResponse:
    """Encola sincronización de licitaciones activas desde ChileCompra.

    Idempotente: si hay un sync en curso, Celery lo gestiona.
    Los resultados tardan ~1 minuto en reflejarse.
    """
    celery_app.send_task("tasks.sync_chilecompra.sync_listado_diario")
    return SyncTriggerResponse(
        status="enqueued",
        message="Sincronización iniciada. Los resultados estarán disponibles en ~1 minuto.",
        enqueued_at=datetime.now(UTC),
    )
