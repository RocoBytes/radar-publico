"""Endpoints REST para la gestión de radares de búsqueda.

GET    /api/v1/radares          — lista los radares de la empresa
POST   /api/v1/radares          — crea un radar
GET    /api/v1/radares/{id}     — detalle de un radar
PATCH  /api/v1/radares/{id}     — actualización parcial
DELETE /api/v1/radares/{id}     — elimina un radar
"""

from datetime import UTC, datetime
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep, EmpresaDep
from app.models.radar import Radar
from app.schemas.radar import (
    RadarCreateRequest,
    RadarListResponse,
    RadarResponse,
    RadarUpdateRequest,
)

router = APIRouter(prefix="/radares", tags=["radares"])

_MAX_RADARES_POR_EMPRESA = 20


async def _get_radar_de_empresa_o_404(
    radar_id: uuid.UUID, empresa_id: uuid.UUID, db: DbDep
) -> Radar:
    result = await db.execute(select(Radar).where(Radar.id == radar_id))
    radar = result.scalar_one_or_none()
    if radar is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Radar '{radar_id}' no encontrado",
        )
    if radar.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés permiso para acceder a este radar",
        )
    return radar


@router.get("", response_model=RadarListResponse)
async def listar_radares(
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> RadarListResponse:
    """Lista todos los radares de la empresa, ordenados por created_at DESC."""

    result = await db.execute(
        select(Radar)
        .where(Radar.empresa_id == empresa.id)
        .order_by(Radar.created_at.desc())
    )
    radares = list(result.scalars().all())

    return RadarListResponse(
        items=[RadarResponse.model_validate(r) for r in radares],
        total=len(radares),
    )


@router.post("", response_model=RadarResponse, status_code=status.HTTP_201_CREATED)
async def crear_radar(
    data: RadarCreateRequest,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> RadarResponse:
    """Crea un nuevo radar para la empresa del usuario autenticado.

    Levanta 400 si se alcanza el límite de 50 radares por empresa.
    """

    count_result = await db.execute(
        select(func.count()).where(Radar.empresa_id == empresa.id)
    )
    if count_result.scalar_one() >= _MAX_RADARES_POR_EMPRESA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Se alcanzó el límite de {_MAX_RADARES_POR_EMPRESA} "
                "radares por empresa"
            ),
        )

    radar = Radar(
        empresa_id=empresa.id,
        nombre=data.nombre,
        descripcion=data.descripcion,
        filtros=data.filtros.model_dump(exclude_none=True),
        notif_canal=data.notif_canal,
        notif_frecuencia=data.notif_frecuencia,
        notif_score_minimo=data.notif_score_minimo,
    )
    db.add(radar)
    await db.commit()
    await db.refresh(radar)

    return RadarResponse.model_validate(radar)


@router.get("/{radar_id}", response_model=RadarResponse)
async def obtener_radar(
    radar_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> RadarResponse:
    """Retorna el detalle de un radar por UUID."""
    radar = await _get_radar_de_empresa_o_404(radar_id, empresa.id, db)
    return RadarResponse.model_validate(radar)


@router.patch("/{radar_id}", response_model=RadarResponse)
async def actualizar_radar(
    radar_id: uuid.UUID,
    data: RadarUpdateRequest,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> RadarResponse:
    """Actualiza parcialmente un radar. Solo se aplican los campos enviados."""
    radar = await _get_radar_de_empresa_o_404(radar_id, empresa.id, db)

    if data.nombre is not None:
        radar.nombre = data.nombre
    if data.descripcion is not None:
        radar.descripcion = data.descripcion
    if data.filtros is not None:
        radar.filtros = data.filtros.model_dump(exclude_none=True)
    if data.activo is not None:
        radar.activo = data.activo
    if data.notif_canal is not None:
        radar.notif_canal = data.notif_canal
    if data.notif_frecuencia is not None:
        radar.notif_frecuencia = data.notif_frecuencia
    if data.notif_score_minimo is not None:
        radar.notif_score_minimo = data.notif_score_minimo

    radar.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(radar)

    return RadarResponse.model_validate(radar)


@router.delete("/{radar_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_radar(
    radar_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> None:
    """Elimina un radar por UUID.

    Levanta 404 si el radar no existe.
    Levanta 403 si el radar pertenece a otra empresa.
    """
    radar = await _get_radar_de_empresa_o_404(radar_id, empresa.id, db)
    await db.delete(radar)
    await db.commit()
