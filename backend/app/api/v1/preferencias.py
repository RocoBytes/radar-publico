"""Endpoints REST para preferencias de notificaciones de la empresa.

GET   /preferencias-notificaciones  — retorna preferencias (crea defaults si no existen)
PATCH /preferencias-notificaciones  — actualización parcial de campos
"""

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep, EmpresaDep
from app.models.preferencias import PreferenciasNotificaciones
from app.schemas.preferencias import PreferenciasResponse, PreferenciasUpdateRequest

router = APIRouter(
    prefix="/preferencias-notificaciones",
    tags=["configuracion"],
)


async def _get_o_crear_preferencias(
    db: DbDep,
    empresa: EmpresaDep,
) -> PreferenciasNotificaciones:
    """Carga las preferencias de la empresa o las crea con defaults si no existen."""
    result = await db.execute(
        select(PreferenciasNotificaciones).where(
            PreferenciasNotificaciones.empresa_id == empresa.id
        )
    )
    preferencias = result.scalar_one_or_none()

    if preferencias is None:
        preferencias = PreferenciasNotificaciones(empresa_id=empresa.id)
        db.add(preferencias)
        await db.commit()
        await db.refresh(preferencias)

    return preferencias


@router.get("", response_model=PreferenciasResponse)
async def obtener_preferencias(
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> PreferenciasResponse:
    """Retorna las preferencias de notificación de la empresa del usuario autenticado.

    Si todavía no existen, las crea con los valores por defecto definidos en BD.
    """
    preferencias = await _get_o_crear_preferencias(db, empresa)
    return PreferenciasResponse.model_validate(preferencias)


@router.patch("", response_model=PreferenciasResponse)
async def actualizar_preferencias(
    data: PreferenciasUpdateRequest,
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> PreferenciasResponse:
    """Actualiza parcialmente las preferencias de notificación de la empresa.

    Solo aplica los campos presentes en el request (PATCH parcial).
    """
    preferencias = await _get_o_crear_preferencias(db, empresa)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(preferencias, field, value)

    preferencias.updated_at = datetime.now(UTC)

    db.add(preferencias)
    await db.commit()
    await db.refresh(preferencias)

    return PreferenciasResponse.model_validate(preferencias)
