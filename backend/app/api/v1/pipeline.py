"""Endpoints REST para el pipeline de seguimiento de licitaciones.

GET    /api/v1/pipeline            — listado paginado con filtros
GET    /api/v1/pipeline/{id}       — detalle con notas
PATCH  /api/v1/pipeline/{id}       — actualizar estado y campos de seguimiento
POST   /api/v1/pipeline/{id}/notas — agregar una nota al ítem
DELETE /api/v1/pipeline/{id}/notas/{nota_id} — eliminar una nota
"""

from datetime import UTC, datetime
import math
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbDep, EmpresaDep
from app.models.enums import PipelineEstado
from app.models.licitacion import Licitacion
from app.models.pipeline import PipelineItem, PipelineNota
from app.schemas.pipeline import (
    LicitacionEnPipelineResponse,
    PipelineItemListItem,
    PipelineItemResponse,
    PipelineItemUpdateRequest,
    PipelineListResponse,
    PipelineNotaCreateRequest,
    PipelineNotaResponse,
)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


async def _get_item_de_empresa_o_404(
    item_id: uuid.UUID,
    empresa_id: uuid.UUID,
    db: DbDep,
    *,
    con_notas: bool = False,
) -> PipelineItem:
    opts = [
        selectinload(PipelineItem.licitacion).options(
            selectinload(Licitacion.organismo)
        ),
    ]
    if con_notas:
        opts.append(selectinload(PipelineItem.notas))

    result = await db.execute(
        select(PipelineItem)
        .where(PipelineItem.id == item_id)
        .options(*opts)
    )
    item = result.scalar_one_or_none()

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline item '{item_id}' no encontrado",
        )
    if item.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés permiso para acceder a este ítem",
        )
    return item


def _licitacion_response(licitacion: Licitacion) -> LicitacionEnPipelineResponse:
    return LicitacionEnPipelineResponse(
        codigo=licitacion.codigo,
        nombre=licitacion.nombre,
        estado=licitacion.estado,
        tipo=licitacion.tipo,
        moneda=licitacion.moneda,
        monto_estimado=licitacion.monto_estimado,
        fecha_publicacion=licitacion.fecha_publicacion,
        fecha_cierre=licitacion.fecha_cierre,
        organismo_nombre=(
            licitacion.organismo.nombre if licitacion.organismo else None
        ),
    )


def _build_list_item(item: PipelineItem, notas_count: int) -> PipelineItemListItem:
    return PipelineItemListItem(
        id=item.id,
        estado=item.estado,
        score=item.score,
        score_justificacion=item.score_justificacion,
        razon_descarte=item.razon_descarte,
        monto_postulado=(
            float(item.monto_postulado) if item.monto_postulado is not None else None
        ),
        resultado_observaciones=item.resultado_observaciones,
        detected_by_radar_id=item.detected_by_radar_id,
        notas_count=notas_count,
        created_at=item.created_at,
        updated_at=item.updated_at,
        licitacion=_licitacion_response(item.licitacion),
    )


def _build_detail(item: PipelineItem) -> PipelineItemResponse:
    return PipelineItemResponse(
        id=item.id,
        estado=item.estado,
        score=item.score,
        score_justificacion=item.score_justificacion,
        razon_descarte=item.razon_descarte,
        monto_postulado=(
            float(item.monto_postulado) if item.monto_postulado is not None else None
        ),
        resultado_observaciones=item.resultado_observaciones,
        detected_by_radar_id=item.detected_by_radar_id,
        notas_count=len(item.notas),
        created_at=item.created_at,
        updated_at=item.updated_at,
        licitacion=_licitacion_response(item.licitacion),
        notas=[PipelineNotaResponse.model_validate(n) for n in item.notas],
    )


# ---------------------------------------------------------------------------
# GET /pipeline
# ---------------------------------------------------------------------------


@router.get("", response_model=PipelineListResponse)
async def listar_pipeline(
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
    estado: PipelineEstado | None = Query(default=None),  # noqa: B008
    score_min: int | None = Query(default=None, ge=0, le=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> PipelineListResponse:
    """Lista los ítems del pipeline de la empresa, ordenados por score DESC.

    Filtra opcionalmente por estado y score_min.
    """

    base = select(PipelineItem).where(PipelineItem.empresa_id == empresa.id)
    if estado is not None:
        base = base.where(PipelineItem.estado == estado)
    if score_min is not None:
        base = base.where(PipelineItem.score >= score_min)

    # Total para la paginación
    count_result = await db.execute(
        select(func.count()).select_from(base.subquery())
    )
    total = count_result.scalar_one()

    # Página de ítems con relaciones
    items_result = await db.execute(
        base.order_by(
            PipelineItem.score.desc().nulls_last(),
            PipelineItem.created_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .options(
            selectinload(PipelineItem.licitacion).options(
                selectinload(Licitacion.organismo)
            ),
            selectinload(PipelineItem.notas),
        )
    )
    items = list(items_result.scalars().all())

    return PipelineListResponse(
        items=[_build_list_item(item, len(item.notas)) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size),
    )


# ---------------------------------------------------------------------------
# GET /pipeline/{id}
# ---------------------------------------------------------------------------


@router.get("/{item_id}", response_model=PipelineItemResponse)
async def obtener_pipeline_item(
    item_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> PipelineItemResponse:
    """Retorna el detalle completo de un ítem del pipeline, incluyendo sus notas."""
    item = await _get_item_de_empresa_o_404(item_id, empresa.id, db, con_notas=True)
    return _build_detail(item)


# ---------------------------------------------------------------------------
# PATCH /pipeline/{id}
# ---------------------------------------------------------------------------


@router.patch("/{item_id}", response_model=PipelineItemResponse)
async def actualizar_pipeline_item(
    item_id: uuid.UUID,
    data: PipelineItemUpdateRequest,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> PipelineItemResponse:
    """Actualiza parcialmente un ítem del pipeline.

    Campos actualizables: estado, razon_descarte, monto_postulado,
    resultado_observaciones.
    """
    item = await _get_item_de_empresa_o_404(item_id, empresa.id, db, con_notas=True)

    if data.estado is not None:
        item.estado = data.estado
    if data.razon_descarte is not None:
        item.razon_descarte = data.razon_descarte
    if data.monto_postulado is not None:
        item.monto_postulado = data.monto_postulado
    if data.resultado_observaciones is not None:
        item.resultado_observaciones = data.resultado_observaciones

    item.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(item)

    # Recargar con relaciones después del commit
    item = await _get_item_de_empresa_o_404(item_id, empresa.id, db, con_notas=True)
    return _build_detail(item)


# ---------------------------------------------------------------------------
# POST /pipeline/{id}/notas
# ---------------------------------------------------------------------------


@router.post(
    "/{item_id}/notas",
    response_model=PipelineNotaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_nota(
    item_id: uuid.UUID,
    data: PipelineNotaCreateRequest,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> PipelineNotaResponse:
    """Agrega una nota textual a un ítem del pipeline."""
    await _get_item_de_empresa_o_404(item_id, empresa.id, db)

    nota = PipelineNota(pipeline_item_id=item_id, contenido=data.contenido)
    db.add(nota)
    await db.commit()
    await db.refresh(nota)

    return PipelineNotaResponse.model_validate(nota)


# ---------------------------------------------------------------------------
# DELETE /pipeline/{id}/notas/{nota_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{item_id}/notas/{nota_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def eliminar_nota(
    item_id: uuid.UUID,
    nota_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> None:
    """Elimina una nota de un ítem del pipeline."""
    await _get_item_de_empresa_o_404(item_id, empresa.id, db)

    result = await db.execute(
        select(PipelineNota).where(PipelineNota.id == nota_id)
    )
    nota = result.scalar_one_or_none()

    if nota is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nota '{nota_id}' no encontrada",
        )
    if nota.pipeline_item_id != item_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La nota no pertenece a este ítem",
        )

    await db.delete(nota)
    await db.commit()
