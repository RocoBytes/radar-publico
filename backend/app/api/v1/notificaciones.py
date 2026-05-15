"""Endpoints REST para notificaciones in-app.

GET  /api/v1/notificaciones/resumen       — últimas 10 in_app + unread_count
POST /api/v1/notificaciones/{id}/leer     — marca una notificación como leída
"""

from datetime import UTC, datetime
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep, EmpresaDep
from app.models.enums import NotifCanal, NotifStatus
from app.models.notificacion import Notificacion
from app.schemas.notificacion import NotificacionesResumenResponse, NotificacionResponse

router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])

_LIMIT_RESUMEN = 10


@router.get("/resumen", response_model=NotificacionesResumenResponse)
async def obtener_resumen(
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> NotificacionesResumenResponse:
    """Retorna las últimas 10 notificaciones in_app de la empresa + unread_count."""

    # Conteo de no leídas
    unread_result = await db.execute(
        select(func.count())
        .select_from(Notificacion)
        .where(
            Notificacion.empresa_id == empresa.id,
            Notificacion.canal == NotifCanal.in_app,
            Notificacion.leida_at.is_(None),
        )
    )
    unread_count: int = unread_result.scalar_one()

    # Últimas 10 notificaciones in_app
    items_result = await db.execute(
        select(Notificacion)
        .where(
            Notificacion.empresa_id == empresa.id,
            Notificacion.canal == NotifCanal.in_app,
        )
        .order_by(Notificacion.created_at.desc())
        .limit(_LIMIT_RESUMEN)
    )
    items = list(items_result.scalars().all())

    return NotificacionesResumenResponse(
        unread_count=unread_count,
        items=[NotificacionResponse.model_validate(n) for n in items],
    )


@router.post("/{notif_id}/leer", response_model=NotificacionResponse)
async def marcar_leida(
    notif_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> NotificacionResponse:
    """Marca una notificación in_app como leída.

    Levanta 404 si la notificación no existe o no pertenece a la empresa.
    Solo aplica a notificaciones de canal in_app.
    """

    result = await db.execute(
        select(Notificacion).where(Notificacion.id == notif_id)
    )
    notif = result.scalar_one_or_none()

    if notif is None or notif.empresa_id != empresa.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada",
        )

    if notif.canal == NotifCanal.in_app:
        notif.leida_at = datetime.now(UTC)
        notif.status = NotifStatus.leida
        await db.commit()
        await db.refresh(notif)

    return NotificacionResponse.model_validate(notif)
