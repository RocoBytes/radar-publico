"""Endpoints REST para la gestión de intereses comerciales.

GET    /api/v1/intereses          — lista los intereses de la empresa
POST   /api/v1/intereses          — agrega un interés
DELETE /api/v1/intereses/{id}     — elimina un interés por UUID
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep
from app.models.empresa import Empresa
from app.models.interes import Interes
from app.schemas.intereses import (
    InteresCreateRequest,
    InteresListResponse,
    InteresResponse,
)

router = APIRouter(prefix="/intereses", tags=["intereses"])

# Límite máximo de intereses por empresa para no saturar el sistema de scoring
_MAX_INTERESES_POR_EMPRESA = 200


async def _get_empresa_o_404(
    db: DbDep,
    current_user: CurrentUser,
) -> Empresa:
    """Carga la empresa del usuario o lanza 404 si no existe."""
    result = await db.execute(select(Empresa).where(Empresa.usuario_id == current_user.id))
    empresa = result.scalar_one_or_none()
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada para este usuario",
        )
    return empresa


@router.get("", response_model=InteresListResponse)
async def listar_intereses(
    db: DbDep,
    current_user: CurrentUser,
) -> InteresListResponse:
    """Lista todos los intereses de la empresa del usuario autenticado.

    Ordena por created_at DESC.
    """
    empresa = await _get_empresa_o_404(db, current_user)

    result = await db.execute(
        select(Interes).where(Interes.empresa_id == empresa.id).order_by(Interes.created_at.desc())
    )
    intereses = list(result.scalars().all())

    return InteresListResponse(
        items=[InteresResponse.model_validate(i) for i in intereses],
        total=len(intereses),
    )


@router.post("", response_model=InteresResponse, status_code=status.HTTP_201_CREATED)
async def crear_interes(
    data: InteresCreateRequest,
    db: DbDep,
    current_user: CurrentUser,
) -> InteresResponse:
    """Agrega un interés comercial a la empresa del usuario autenticado.

    Levanta 409 si ya existe el mismo (empresa_id, tipo, valor).
    Levanta 400 si se alcanza el límite de 200 intereses por empresa.
    """
    empresa = await _get_empresa_o_404(db, current_user)

    # Verificar unicidad antes de insertar
    existente = await db.execute(
        select(Interes).where(
            Interes.empresa_id == empresa.id,
            Interes.tipo == data.tipo,
            Interes.valor == data.valor,
        )
    )
    if existente.scalar_one_or_none() is not None:
        msg = (
            "Esta palabra clave ya está en tus intereses."
            if data.tipo.value == "keyword"
            else "Este rubro ya está en tus intereses."
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)

    # Verificar límite de intereses por empresa
    count_result = await db.execute(select(func.count()).where(Interes.empresa_id == empresa.id))
    total = count_result.scalar_one()
    if total >= _MAX_INTERESES_POR_EMPRESA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Se alcanzó el límite de {_MAX_INTERESES_POR_EMPRESA} " "intereses por empresa"
            ),
        )

    interes = Interes(
        empresa_id=empresa.id,
        tipo=data.tipo,
        valor=data.valor,
        prioridad=data.prioridad,
    )
    db.add(interes)
    await db.commit()
    await db.refresh(interes)

    return InteresResponse.model_validate(interes)


@router.delete(
    "/{interes_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def eliminar_interes(
    interes_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
) -> None:
    """Elimina un interés por UUID.

    Levanta 404 si el interés no existe.
    Levanta 403 si el interés pertenece a otra empresa.
    """
    empresa = await _get_empresa_o_404(db, current_user)

    result = await db.execute(select(Interes).where(Interes.id == interes_id))
    interes = result.scalar_one_or_none()

    if interes is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interés '{interes_id}' no encontrado",
        )

    # Verificar que el interés pertenece a la empresa del usuario
    if interes.empresa_id != empresa.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés permiso para eliminar este interés",
        )

    await db.delete(interes)
    await db.commit()
