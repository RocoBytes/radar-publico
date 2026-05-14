"""Endpoints REST para el perfil de empresa del usuario autenticado.

GET  /api/v1/empresa/me  — retorna la empresa del proveedor
PATCH /api/v1/empresa/me — actualiza datos editables de la empresa
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.models.empresa import Empresa
from app.schemas.empresa import EmpresaResponse, EmpresaUpdateRequest

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

    return EmpresaResponse.model_validate(empresa)
