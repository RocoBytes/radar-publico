"""Endpoints REST para el checklist documental de un pipeline_item.

GET    /pipeline/{pipeline_item_id}/checklist
POST   /pipeline/{pipeline_item_id}/checklist
PATCH  /pipeline/{pipeline_item_id}/checklist/{item_id}
DELETE /pipeline/{pipeline_item_id}/checklist/{item_id}
POST   /pipeline/{pipeline_item_id}/checklist/bootstrap-from-analysis

Todos los endpoints están protegidos por feature flag FEATURE_PIPELINE_CHECKLIST.
Si el flag está apagado se retorna 503.
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbDep, EmpresaDep
from app.config import settings
from app.schemas.checklist import (
    ChecklistBootstrapResponse,
    ChecklistItemCreate,
    ChecklistItemResponse,
    ChecklistItemUpdate,
)
from app.services.pipeline import checklist as checklist_service

router = APIRouter(prefix="/pipeline", tags=["pipeline-checklist"])

_FLAG_APAGADO = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="Feature no disponible",
)


# ---------------------------------------------------------------------------
# GET /pipeline/{pipeline_item_id}/checklist
# ---------------------------------------------------------------------------


@router.get(
    "/{pipeline_item_id}/checklist",
    response_model=list[ChecklistItemResponse],
)
async def listar_checklist(
    pipeline_item_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[ChecklistItemResponse]:
    """Lista los ítems del checklist de un pipeline_item, ordenados por orden ASC."""
    if not settings.feature_pipeline_checklist:
        raise _FLAG_APAGADO

    items = await checklist_service.get_items(
        db, pipeline_item_id, empresa.id, limit=limit, offset=offset
    )
    return [ChecklistItemResponse.model_validate(i) for i in items]


# ---------------------------------------------------------------------------
# POST /pipeline/{pipeline_item_id}/checklist
# ---------------------------------------------------------------------------


@router.post(
    "/{pipeline_item_id}/checklist",
    response_model=ChecklistItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_checklist_item(
    pipeline_item_id: uuid.UUID,
    data: ChecklistItemCreate,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> ChecklistItemResponse:
    """Crea un ítem manual en el checklist. El origen queda forzado a 'manual'."""
    if not settings.feature_pipeline_checklist:
        raise _FLAG_APAGADO

    item = await checklist_service.create_item(db, pipeline_item_id, empresa.id, data)
    return ChecklistItemResponse.model_validate(item)


# ---------------------------------------------------------------------------
# PATCH /pipeline/{pipeline_item_id}/checklist/{item_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/{pipeline_item_id}/checklist/{item_id}",
    response_model=ChecklistItemResponse,
)
async def actualizar_checklist_item(
    pipeline_item_id: uuid.UUID,
    item_id: uuid.UUID,
    data: ChecklistItemUpdate,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> ChecklistItemResponse:
    """Actualiza parcialmente un ítem del checklist.

    Si estado cambia a 'completado' y completed_at es None, lo setea.
    Si estado sale de 'completado', limpia completed_at.
    """
    if not settings.feature_pipeline_checklist:
        raise _FLAG_APAGADO

    item = await checklist_service.update_item(db, pipeline_item_id, item_id, empresa.id, data)
    return ChecklistItemResponse.model_validate(item)


# ---------------------------------------------------------------------------
# DELETE /pipeline/{pipeline_item_id}/checklist/{item_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{pipeline_item_id}/checklist/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def eliminar_checklist_item(
    pipeline_item_id: uuid.UUID,
    item_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> Response:
    """Elimina un ítem del checklist. Registra auditoría."""
    if not settings.feature_pipeline_checklist:
        raise _FLAG_APAGADO

    await checklist_service.delete_item(db, pipeline_item_id, item_id, empresa.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# POST /pipeline/{pipeline_item_id}/checklist/bootstrap-from-analysis
# ---------------------------------------------------------------------------


@router.post(
    "/{pipeline_item_id}/checklist/bootstrap-from-analysis",
    response_model=ChecklistBootstrapResponse,
)
async def bootstrap_checklist_desde_analisis(
    pipeline_item_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> ChecklistBootstrapResponse:
    """Inicializa el checklist desde documentos_obligatorios del análisis IA.

    Es idempotente: si ya existen ítems IA, no se duplican.
    Si no hay análisis disponible, retorna lista vacía sin error.
    """
    if not settings.feature_pipeline_checklist:
        raise _FLAG_APAGADO

    return await checklist_service.bootstrap_from_analysis(db, pipeline_item_id, empresa.id)
