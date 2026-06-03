"""Endpoints de directorios de organismos compradores y proveedores.

GET /api/v1/directorios/organismos — listado paginado de organismos con métricas
GET /api/v1/directorios/proveedores — listado paginado de proveedores con métricas

Ambos endpoints requieren usuario autenticado y agregan datos de los últimos 2 años.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep  # noqa: TCH001
from app.models.adjudicacion import Adjudicacion
from app.models.licitacion import Licitacion
from app.models.organismo import Organismo
from app.models.proveedor import Proveedor

router = APIRouter(prefix="/directorios", tags=["directorios"])

# Ventana histórica para agregaciones
_VENTANA_DIAS: int = 730

# Límite máximo de page_size permitido
_MAX_PAGE_SIZE: int = 100


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class OrganismoListItem(BaseModel):
    codigo_organismo: int
    nombre: str
    ministerio: str | None
    region: str | None
    total_licitaciones: int
    monto_total_adjudicado: float | None
    proveedores_distintos: int


class OrganismosResponse(BaseModel):
    items: list[OrganismoListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProveedorListItem(BaseModel):
    rut: str
    razon_social: str
    nombre_fantasia: str | None
    licitaciones_ganadas: int
    monto_total: float | None


class ProveedoresResponse(BaseModel):
    items: list[ProveedorListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/organismos", response_model=OrganismosResponse)
async def listar_organismos(
    db: DbDep,
    _current_user: CurrentUser,
    q: str = Query(default="", description="Filtro por nombre (ILIKE)"),
    region: str | None = Query(default=None, description="Filtro exacto por región"),
    page: int = Query(default=1, ge=1, description="Número de página"),
    page_size: int = Query(default=25, ge=1, le=_MAX_PAGE_SIZE, description="Ítems por página"),
) -> OrganismosResponse:
    """Retorna organismos compradores con métricas de actividad de los últimos 2 años.

    Incluye total de licitaciones publicadas, monto total adjudicado y cantidad
    de proveedores distintos que ganaron licitaciones en el organismo.
    Ordenado por total de licitaciones descendente.
    """
    fecha_limite = datetime.now(UTC) - timedelta(days=_VENTANA_DIAS)

    # Subquery: licitaciones del período por organismo
    lics_periodo = (
        select(Licitacion.codigo, Licitacion.codigo_organismo)
        .where(
            Licitacion.fecha_publicacion >= fecha_limite,
            Licitacion.codigo_organismo.is_not(None),
        )
        .subquery()
    )

    # Query base con agregaciones
    base_stmt = (
        select(
            Organismo.codigo_organismo,
            Organismo.nombre,
            Organismo.ministerio,
            Organismo.region,
            func.count(lics_periodo.c.codigo.distinct()).label("total_licitaciones"),
            func.sum(Adjudicacion.monto_adjudicado).label("monto_total_adjudicado"),
            func.count(Adjudicacion.rut_proveedor.distinct()).label("proveedores_distintos"),
        )
        .outerjoin(
            lics_periodo,
            lics_periodo.c.codigo_organismo == Organismo.codigo_organismo,
        )
        .outerjoin(
            Adjudicacion,
            Adjudicacion.licitacion_codigo == lics_periodo.c.codigo,
        )
        .group_by(
            Organismo.codigo_organismo,
            Organismo.nombre,
            Organismo.ministerio,
            Organismo.region,
        )
    )

    # Filtros opcionales
    if q:
        base_stmt = base_stmt.where(Organismo.nombre.ilike(f"%{q}%"))
    if region is not None:
        base_stmt = base_stmt.where(Organismo.region == region)

    # Query de conteo total (sobre la misma base)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    # Query paginada con orden
    offset = (page - 1) * page_size
    items_stmt = (
        base_stmt.order_by(func.count(lics_periodo.c.codigo.distinct()).desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(items_stmt)).all()

    items: list[OrganismoListItem] = [
        OrganismoListItem(
            codigo_organismo=row.codigo_organismo,
            nombre=row.nombre,
            ministerio=row.ministerio,
            region=row.region,
            total_licitaciones=int(row.total_licitaciones or 0),
            monto_total_adjudicado=(
                float(row.monto_total_adjudicado)
                if row.monto_total_adjudicado is not None
                else None
            ),
            proveedores_distintos=int(row.proveedores_distintos or 0),
        )
        for row in rows
    ]

    total_pages = max(1, -(-total // page_size))  # división techo sin math.ceil
    return OrganismosResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/proveedores", response_model=ProveedoresResponse)
async def listar_proveedores(
    db: DbDep,
    _current_user: CurrentUser,
    q: str = Query(default="", description="Filtro por razón social (ILIKE)"),
    page: int = Query(default=1, ge=1, description="Número de página"),
    page_size: int = Query(default=25, ge=1, le=_MAX_PAGE_SIZE, description="Ítems por página"),
) -> ProveedoresResponse:
    """Retorna proveedores con adjudicaciones en los últimos 2 años.

    Solo incluye proveedores con al menos una adjudicación en el período.
    Incluye total de licitaciones ganadas y monto total adjudicado.
    Ordenado por licitaciones ganadas descendente.
    """
    fecha_limite = datetime.now(UTC) - timedelta(days=_VENTANA_DIAS)

    # Query base: proveedores con adjudicaciones en el período
    base_stmt = (
        select(
            Proveedor.rut,
            Proveedor.razon_social,
            Proveedor.nombre_fantasia,
            func.count(Adjudicacion.id).label("licitaciones_ganadas"),
            func.sum(Adjudicacion.monto_adjudicado).label("monto_total"),
        )
        .join(Adjudicacion, Adjudicacion.rut_proveedor == Proveedor.rut)
        .where(Adjudicacion.fecha_adjudicacion >= fecha_limite)
        .group_by(Proveedor.rut, Proveedor.razon_social, Proveedor.nombre_fantasia)
        .having(func.count(Adjudicacion.id) > 0)
    )

    # Filtro opcional por razón social
    if q:
        base_stmt = base_stmt.where(Proveedor.razon_social.ilike(f"%{q}%"))

    # Conteo total
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    # Query paginada con orden
    offset = (page - 1) * page_size
    items_stmt = (
        base_stmt.order_by(func.count(Adjudicacion.id).desc()).offset(offset).limit(page_size)
    )
    rows = (await db.execute(items_stmt)).all()

    items: list[ProveedorListItem] = [
        ProveedorListItem(
            rut=row.rut,
            razon_social=row.razon_social,
            nombre_fantasia=row.nombre_fantasia,
            licitaciones_ganadas=int(row.licitaciones_ganadas),
            monto_total=(float(row.monto_total) if row.monto_total is not None else None),
        )
        for row in rows
    ]

    total_pages = max(1, -(-total // page_size))
    return ProveedoresResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
