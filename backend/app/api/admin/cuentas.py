"""Endpoints del panel admin para gestión de cuentas de proveedores.

Todos requieren rol admin (AdminUser dep).
Regla #2: ticket_cifrado nunca sale en ninguna respuesta.
"""

from typing import Annotated
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import AdminUser, DbDep
from app.models.empresa import Empresa
from app.schemas.admin import (
    CambiarEstadoRequest,
    CargarTicketRequest,
    CrearCuentaRequest,
    CuentaCreadaResponse,
    CuentaListResponse,
    CuentaResponse,
    EmpresaResumen,
    ImpersonacionResponse,
    TicketDiagnosticoResponse,
    TicketResponse,
)
from app.services.admin.exceptions import (
    CuentaNoEncontradaError,
    CuentaYaExisteError,
    EmpresaNoEncontradaError,
)
from app.services.admin.service import AdminService

router = APIRouter(prefix="/cuentas", tags=["admin-cuentas"])


def _empresa_resumen(empresa: Empresa | None) -> EmpresaResumen | None:
    """Convierte Empresa ORM a EmpresaResumen."""
    if empresa is None:
        return None
    return EmpresaResumen(
        rut=empresa.rut,
        razon_social=empresa.razon_social,
        tiene_ticket=empresa.ticket is not None,
    )


@router.get("", response_model=CuentaListResponse)
async def listar_cuentas(
    db: DbDep,
    _admin: AdminUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> CuentaListResponse:
    svc = AdminService(db)
    items, total = await svc.listar_cuentas(page=page, page_size=page_size)
    return CuentaListResponse(
        items=[
            CuentaResponse.model_validate(u).model_copy(
                update={"empresa": _empresa_resumen(u.empresa)}
            )
            for u in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=CuentaCreadaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_cuenta(
    payload: CrearCuentaRequest,
    db: DbDep,
    admin: AdminUser,
) -> CuentaCreadaResponse:
    svc = AdminService(db)
    try:
        usuario, temp_password = await svc.crear_cuenta(
            email=str(payload.email),
            rut=payload.rut,
            razon_social=payload.razon_social,
            creado_por_id=admin.id,
        )
    except CuentaYaExisteError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una cuenta con ese {exc.campo}",
        ) from exc

    return CuentaCreadaResponse(
        id=usuario.id,
        email=usuario.email,
        rol=usuario.rol,
        status=usuario.status,
        must_change_password=usuario.must_change_password,
        created_at=usuario.created_at,
        empresa=_empresa_resumen(usuario.empresa),
        temp_password=temp_password,
    )


@router.get("/{usuario_id}", response_model=CuentaResponse)
async def obtener_cuenta(
    usuario_id: uuid.UUID,
    db: DbDep,
    _admin: AdminUser,
) -> CuentaResponse:
    svc = AdminService(db)
    try:
        usuario = await svc.obtener_cuenta(usuario_id)
    except CuentaNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta no encontrada",
        ) from None

    return CuentaResponse.model_validate(usuario).model_copy(
        update={"empresa": _empresa_resumen(usuario.empresa)}
    )


@router.patch("/{usuario_id}/estado", response_model=CuentaResponse)
async def cambiar_estado(
    usuario_id: uuid.UUID,
    payload: CambiarEstadoRequest,
    db: DbDep,
    admin: AdminUser,
) -> CuentaResponse:
    svc = AdminService(db)
    try:
        usuario = await svc.cambiar_estado(
            usuario_id=usuario_id,
            accion=payload.accion,
            admin_id=admin.id,
        )
    except CuentaNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta no encontrada",
        ) from None

    return CuentaResponse.model_validate(usuario).model_copy(
        update={"empresa": _empresa_resumen(usuario.empresa)}
    )


@router.post("/{usuario_id}/ticket", response_model=TicketResponse)
async def cargar_ticket(
    usuario_id: uuid.UUID,
    payload: CargarTicketRequest,
    db: DbDep,
    admin: AdminUser,
) -> TicketResponse:
    svc = AdminService(db)
    try:
        ticket = await svc.cargar_ticket(
            usuario_id=usuario_id,
            ticket_plaintext=payload.ticket,
            admin_id=admin.id,
        )
    except CuentaNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta no encontrada",
        ) from None
    except EmpresaNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El usuario no tiene empresa asociada",
        ) from None

    return TicketResponse.model_validate(ticket)


@router.post("/{usuario_id}/impersonar", response_model=ImpersonacionResponse)
async def impersonar_cuenta(
    usuario_id: uuid.UUID,
    db: DbDep,
    admin: AdminUser,
) -> ImpersonacionResponse:
    """Genera token de impersonación (1h) para operar como el proveedor."""
    svc = AdminService(db)
    try:
        token = await svc.impersonar_cuenta(
            usuario_id=usuario_id,
            admin_id=admin.id,
        )
    except CuentaNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta no encontrada",
        ) from None

    return ImpersonacionResponse(access_token=token)


@router.get("/{usuario_id}/ticket/diagnostico", response_model=TicketDiagnosticoResponse)
async def diagnosticar_ticket(
    usuario_id: uuid.UUID,
    db: DbDep,
    _admin: AdminUser,
    test_conexion: Annotated[bool, Query()] = False,
) -> TicketDiagnosticoResponse:
    """Diagnóstica el ticket ChileCompra: estado, cuota y test opcional de conexión."""
    svc = AdminService(db)
    try:
        result = await svc.diagnosticar_ticket(
            usuario_id=usuario_id,
            test_conexion=test_conexion,
        )
    except CuentaNoEncontradaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta no encontrada",
        ) from None

    return TicketDiagnosticoResponse(**result)
