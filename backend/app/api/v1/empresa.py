"""Endpoints REST para el perfil de empresa del usuario autenticado.

GET  /api/v1/empresa/me              — retorna la empresa del proveedor
PATCH /api/v1/empresa/me             — actualiza datos editables de la empresa
POST /api/v1/empresa/ticket-request  — solicita activación del ticket ChileCompra
GET  /api/v1/empresa/ticket-status   — estado del ticket ChileCompra de la empresa
"""

from datetime import UTC, date, datetime

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select

from app.api.deps import CurrentUser, DbDep
from app.core import cache
from app.models.api_log import ApiQuotaLog
from app.models.empresa import Empresa
from app.models.ticket import TicketApi
from app.schemas.empresa import EmpresaResponse, EmpresaUpdateRequest, TicketStatusResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/empresa", tags=["empresa"])


async def _get_empresa_o_404(
    db: DbDep,
    current_user: CurrentUser,
) -> Empresa:
    """Carga la empresa del usuario o lanza 404 si no existe."""
    result = await db.execute(
        select(Empresa).where(Empresa.usuario_id == current_user.id)
    )
    empresa = result.scalar_one_or_none()
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada para este usuario",
        )
    return empresa


@router.get("/me", response_model=EmpresaResponse)
async def obtener_empresa_me(
    db: DbDep,
    current_user: CurrentUser,
) -> EmpresaResponse:
    """Retorna el perfil de empresa del usuario autenticado.

    Levanta 404 si el usuario no tiene empresa asociada.
    """
    empresa = await _get_empresa_o_404(db, current_user)
    return EmpresaResponse.model_validate(empresa)


@router.patch("/me", response_model=EmpresaResponse)
async def actualizar_empresa_me(
    data: EmpresaUpdateRequest,
    db: DbDep,
    current_user: CurrentUser,
) -> EmpresaResponse:
    """Actualiza datos editables de la empresa del usuario autenticado.

    Solo aplica los campos presentes en el request (PATCH parcial).
    Campos no editables (rut, razon_social, usuario_id) son ignorados
    por el schema y nunca llegan aquí.
    Levanta 404 si el usuario no tiene empresa asociada.
    """
    empresa = await _get_empresa_o_404(db, current_user)

    # Aplicar solo los campos enviados explícitamente en el request
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(empresa, field, value)

    empresa.updated_at = datetime.now(UTC)

    db.add(empresa)
    await db.commit()
    await db.refresh(empresa)

    await cache.delete(f"auth:me:{current_user.id}")

    return EmpresaResponse.model_validate(empresa)


class TicketRequestBody(BaseModel):
    """Cuerpo del request para solicitar activación de ticket ChileCompra."""

    ticket_texto: str


class TicketRequestResponse(BaseModel):
    """Respuesta de la solicitud de ticket."""

    mensaje: str


@router.post("/ticket-request", response_model=TicketRequestResponse)
async def solicitar_ticket(
    data: TicketRequestBody,
    db: DbDep,
    current_user: CurrentUser,
) -> TicketRequestResponse:
    """Recibe un ticket ChileCompra del usuario y notifica al equipo de soporte.

    NO persiste el ticket en la BD — eso lo hace el admin manualmente.
    Solo loguea los últimos 4 caracteres del ticket para trazabilidad,
    respetando la regla de oro #12 (sin PII en logs).
    """
    empresa = await _get_empresa_o_404(db, current_user)

    # Solo loguear los últimos 4 caracteres — regla #12: sin datos sensibles en logs
    ticket_ultimos_4 = data.ticket_texto[-4:] if len(data.ticket_texto) >= 4 else "????"

    logger.warning(
        "ticket_request_recibido",
        empresa_id=str(empresa.id),
        usuario_id=str(current_user.id),
        ticket_ultimos_4=ticket_ultimos_4,
    )

    return TicketRequestResponse(
        mensaje="Solicitud enviada al equipo de soporte"
    )


@router.get("/ticket-status", response_model=TicketStatusResponse)
async def obtener_ticket_status(
    db: DbDep,
    current_user: CurrentUser,
) -> TicketStatusResponse:
    """Estado del ticket ChileCompra de la empresa del usuario autenticado."""
    empresa = await _get_empresa_o_404(db, current_user)

    result = await db.execute(
        select(TicketApi).where(TicketApi.empresa_id == empresa.id)
    )
    ticket = result.scalar_one_or_none()

    if ticket is None:
        return TicketStatusResponse(tiene_ticket=False)

    # Requests de hoy
    hoy = date.today()
    count_result = await db.execute(
        select(func.count(ApiQuotaLog.id)).where(
            and_(
                ApiQuotaLog.ticket_id == ticket.id,
                func.date(ApiQuotaLog.created_at) == hoy,
            )
        )
    )
    requests_hoy: int = count_result.scalar_one()

    return TicketStatusResponse(
        tiene_ticket=True,
        status=ticket.status.value,
        ticket_ultimos_4=ticket.ticket_ultimos_4,
        cargado_at=ticket.cargado_at,
        ultima_validacion_at=ticket.ultima_validacion_at,
        ultimo_error=ticket.ultimo_error,
        cuota_diaria_max=ticket.cuota_diaria_max,
        requests_hoy=requests_hoy,
    )
