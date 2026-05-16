"""Endpoints REST para licitaciones.

GET /api/v1/licitaciones       — listado con filtros y paginación
GET /api/v1/licitaciones/{codigo} — detalle completo con relaciones
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import Select, exists, func, select
from sqlalchemy.orm import joinedload, selectinload

from app.api.deps import CurrentUser, DbDep  # noqa: TCH001
from app.models.enums import LicitacionEstado  # noqa: TCH001
from app.models.licitacion import Licitacion, LicitacionItem
from app.models.organismo import Organismo
from app.schemas.licitaciones import (
    LicitacionDetalleResponse,
    LicitacionListItem,
    LicitacionListResponse,
)

router = APIRouter(prefix="/licitaciones", tags=["licitaciones"])


def _date_to_utc_start(d: date) -> datetime:
    """Convierte date a datetime UTC al inicio del día."""
    return datetime.combine(d, time.min, tzinfo=UTC)


def _date_to_utc_end(d: date) -> datetime:
    """Convierte date a datetime UTC al final del día."""
    return datetime.combine(d, time.max, tzinfo=UTC)


def _apply_filters(
    stmt: Select[Any],
    *,
    q: str | None,
    estado: LicitacionEstado | None,
    tipo: str | None,
    region_codigo: int | None,
    fecha_cierre_desde: date | None,
    fecha_cierre_hasta: date | None,
    monto_min: float | None,
    monto_max: float | None,
    unspsc_codigo: str | None,
) -> Select[Any]:
    """Aplica filtros condicionales a la query de licitaciones."""
    if q:
        stmt = stmt.where(
            Licitacion.search_vector.op("@@")(func.plainto_tsquery("spanish", q))
        )
    if estado is not None:
        stmt = stmt.where(Licitacion.estado == estado)
    if tipo is not None:
        stmt = stmt.where(Licitacion.tipo == tipo)
    if region_codigo is not None:
        # Organismo.region es string — filtramos por codigo_organismo
        # directamente en la licitación (join ya aplicado).
        stmt = stmt.where(Licitacion.codigo_organismo == region_codigo)
    if fecha_cierre_desde is not None:
        stmt = stmt.where(
            Licitacion.fecha_cierre >= _date_to_utc_start(fecha_cierre_desde)
        )
    if fecha_cierre_hasta is not None:
        stmt = stmt.where(
            Licitacion.fecha_cierre <= _date_to_utc_end(fecha_cierre_hasta)
        )
    if monto_min is not None:
        stmt = stmt.where(Licitacion.monto_estimado >= monto_min)
    if monto_max is not None:
        stmt = stmt.where(Licitacion.monto_estimado <= monto_max)
    if unspsc_codigo is not None:
        # EXISTS soporta jerarquía: "73" → segmento, "7310" → familia,
        # "731015" → clase, "73101500" → commodity (UNSPSC §9 CLAUDE.md).
        stmt = stmt.where(
            exists(
                select(LicitacionItem.id).where(
                    LicitacionItem.licitacion_codigo == Licitacion.codigo,
                    LicitacionItem.unspsc_codigo.like(f"{unspsc_codigo}%"),
                )
            )
        )
    return stmt


@router.get("", response_model=LicitacionListResponse)
async def listar_licitaciones(
    db: DbDep,
    _current_user: CurrentUser,
    q: str | None = Query(default=None, description="Búsqueda full-text"),
    estado: LicitacionEstado | None = Query(default=None),  # noqa: B008
    tipo: str | None = Query(
        default=None,
        description="Tipo: L1, LE, LP, LS, CO, AG, CM",
    ),
    region_codigo: int | None = Query(
        default=None,
        description="Código de organismo para filtrar por región",
    ),
    fecha_cierre_desde: date | None = Query(default=None),  # noqa: B008
    fecha_cierre_hasta: date | None = Query(default=None),  # noqa: B008
    monto_min: float | None = Query(default=None, ge=0),
    monto_max: float | None = Query(default=None, ge=0),
    unspsc_codigo: str | None = Query(
        default=None,
        min_length=2,
        max_length=8,
        description=(
            "Código UNSPSC (2-8 dígitos). "
            "Filtra licitaciones con ítems en ese rubro."
        ),
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> LicitacionListResponse:
    """Lista licitaciones con filtros opcionales y paginación.

    Requiere usuario autenticado. Ordena por fecha_publicacion DESC.
    """
    # Base: LEFT OUTER JOIN con organismos para obtener nombre del organismo.
    # El tipo de la columna etiquetada es str en el ORM, pero en OUTER JOIN
    # puede ser None — se maneja en el loop de construcción de items.
    base_stmt: Select[Any] = select(
        Licitacion,
        Organismo.nombre.label("organismo_nombre"),
    ).outerjoin(
        Organismo,
        Licitacion.codigo_organismo == Organismo.codigo_organismo,
    )

    base_stmt = _apply_filters(
        base_stmt,
        q=q,
        estado=estado,
        tipo=tipo,
        region_codigo=region_codigo,
        fecha_cierre_desde=fecha_cierre_desde,
        fecha_cierre_hasta=fecha_cierre_hasta,
        monto_min=monto_min,
        monto_max=monto_max,
        unspsc_codigo=unspsc_codigo,
    )

    # COUNT separado — no usar len() sobre los resultados paginados
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    # Query paginada con orden estable
    paginated_stmt = (
        base_stmt.order_by(Licitacion.fecha_publicacion.desc().nullslast())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(paginated_stmt)).all()

    items: list[LicitacionListItem] = []
    for row in rows:
        licitacion: Licitacion = row[0]
        organismo_nombre: str | None = row[1]
        item = LicitacionListItem.model_validate(licitacion)
        item.organismo_nombre = organismo_nombre
        items.append(item)

    return LicitacionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{codigo}", response_model=LicitacionDetalleResponse)
async def obtener_licitacion(
    codigo: str,
    db: DbDep,
    _current_user: CurrentUser,
) -> LicitacionDetalleResponse:
    """Detalle completo de una licitación con items, fechas y criterios.

    Levanta 404 si el código no existe.
    """
    stmt = (
        select(Licitacion)
        .where(Licitacion.codigo == codigo)
        .options(
            joinedload(Licitacion.organismo),
            selectinload(Licitacion.items),
            selectinload(Licitacion.fechas),
            selectinload(Licitacion.criterios),
        )
    )
    licitacion: Licitacion | None = (
        (await db.execute(stmt)).unique().scalar_one_or_none()
    )

    if licitacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Licitación '{codigo}' no encontrada",
        )

    response = LicitacionDetalleResponse.model_validate(licitacion)
    if licitacion.organismo is not None:
        org = licitacion.organismo
        response.organismo_nombre = org.nombre
        response.organismo_rut = org.rut
        response.organismo_region = org.region
        response.organismo_comuna = org.comuna
        response.organismo_direccion = org.direccion
        response.organismo_ministerio = org.ministerio
    return response
