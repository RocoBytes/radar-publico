"""Endpoints REST para licitaciones.

GET /api/v1/licitaciones       — listado con filtros y paginación
GET /api/v1/licitaciones/{codigo} — detalle completo con relaciones
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import Select, func, select  # func: plainto_tsquery en _apply_filters
from sqlalchemy.orm import defer, joinedload, selectinload
import structlog

from app.api.deps import CurrentUser, DbDep  # noqa: TCH001
from app.celery_app import celery_app
from app.core import cache
from app.models.catalogos import Region
from app.models.enums import LicitacionEstado  # noqa: TCH001
from app.models.licitacion import Licitacion
from app.models.organismo import Organismo
from app.schemas.licitaciones import (
    LicitacionDetalleResponse,
    LicitacionListItem,
    LicitacionListResponse,
)

router = APIRouter(prefix="/licitaciones", tags=["licitaciones"])
logger = structlog.get_logger()

# Columnas pesadas que no se necesitan en el listado (embedding ~4KB, raw_payload variable)
_DEFER_LIST = [
    defer(Licitacion.embedding),
    defer(Licitacion.search_vector),
    defer(Licitacion.raw_payload),
    defer(Licitacion.descripcion),
]


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
    region_codigo: str | None,
    fecha_cierre_desde: date | None,
    fecha_cierre_hasta: date | None,
    monto_min: float | None,
    monto_max: float | None,
    unspsc_codigo: str | None,
) -> Select[Any]:
    """Aplica filtros condicionales a la query de licitaciones."""
    if q:
        stmt = stmt.where(Licitacion.search_vector.op("@@")(func.plainto_tsquery("spanish", q)))
    if estado is not None:
        stmt = stmt.where(Licitacion.estado == estado)
    if tipo is not None:
        stmt = stmt.where(Licitacion.tipo == tipo)
    if region_codigo is not None:
        # Subquery: traduce Region.codigo → Region.nombre para comparar con
        # Organismo.region (que almacena el nombre tal como viene de la API).
        nombre_subq = select(Region.nombre).where(Region.codigo == region_codigo).scalar_subquery()
        stmt = stmt.where(Organismo.region == nombre_subq)
    if fecha_cierre_desde is not None:
        stmt = stmt.where(Licitacion.fecha_cierre >= _date_to_utc_start(fecha_cierre_desde))
    if fecha_cierre_hasta is not None:
        stmt = stmt.where(Licitacion.fecha_cierre <= _date_to_utc_end(fecha_cierre_hasta))
    if monto_min is not None:
        stmt = stmt.where(Licitacion.monto_estimado >= monto_min)
    if monto_max is not None:
        stmt = stmt.where(Licitacion.monto_estimado <= monto_max)
    if unspsc_codigo is not None:
        # GIN @> en O(log N) — reemplaza el correlated EXISTS + LIKE que hacía
        # sequential scan con locales UTF-8. unspsc_prefijos contiene todos los
        # niveles del estándar (segmento 2D, familia 4D, clase 6D, commodity 8D).
        stmt = stmt.where(Licitacion.unspsc_prefijos.contains([unspsc_codigo]))
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
    region_codigo: str | None = Query(
        default=None,
        description="Código de región (ej: '13', 'RM'). Filtra por región del organismo comprador.",
    ),
    fecha_cierre_desde: date | None = Query(default=None),  # noqa: B008
    fecha_cierre_hasta: date | None = Query(default=None),  # noqa: B008
    monto_min: float | None = Query(default=None, ge=0),
    monto_max: float | None = Query(default=None, ge=0),
    unspsc_codigo: str | None = Query(
        default=None,
        min_length=2,
        max_length=8,
        description=("Código UNSPSC (2-8 dígitos). " "Filtra licitaciones con ítems en ese rubro."),
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

    # Consultar page_size+1 para detectar si hay página siguiente — sin COUNT(*)
    paginated_stmt = (
        base_stmt.options(*_DEFER_LIST)
        .order_by(Licitacion.fecha_publicacion.desc().nullslast())
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
    )
    rows = (await db.execute(paginated_stmt)).all()

    has_next = len(rows) > page_size
    rows = rows[:page_size]

    items: list[LicitacionListItem] = []
    for row in rows:
        licitacion: Licitacion = row[0]
        organismo_nombre: str | None = row[1]
        item = LicitacionListItem.model_validate(licitacion)
        item.organismo_nombre = organismo_nombre
        items.append(item)

    return LicitacionListResponse(
        items=items,
        has_next=has_next,
        page=page,
        page_size=page_size,
    )


_CACHE_TTL_DETALLE = 600  # 10 minutos


@router.get("/{codigo}", response_model=LicitacionDetalleResponse)
async def obtener_licitacion(
    codigo: str,
    db: DbDep,
    _current_user: CurrentUser,
) -> LicitacionDetalleResponse:
    """Detalle completo de una licitación con items, fechas y criterios.

    Levanta 404 si el código no existe.
    """
    # Cache hit solo cuando el detalle está completamente sincronizado.
    # Si está pendiente no cacheamos — hay side-effects (encola sync_detalle).
    cache_key = f"lic:{codigo}"
    cached_raw = await cache.get(cache_key)
    if cached_raw is not None:
        return LicitacionDetalleResponse.model_validate_json(cached_raw)

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
    licitacion: Licitacion | None = (await db.execute(stmt)).unique().scalar_one_or_none()

    if licitacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Licitación '{codigo}' no encontrada",
        )

    # Si el detalle no está sincronizado, encolar la tarea en background y
    # retornar inmediatamente con los datos parciales disponibles. El cliente
    # debe reintentar cuando detalle_pendiente es True.
    if licitacion.detalle_sincronizado_at is None:
        celery_app.send_task(
            "tasks.sync_detalle.sync_detalle_licitacion",
            args=[codigo],
        )
        logger.debug("sync_detalle_enqueued", codigo=codigo)

    response = LicitacionDetalleResponse.model_validate(licitacion)
    if licitacion.detalle_sincronizado_at is None:
        response.detalle_pendiente = True
    if licitacion.organismo is not None:
        org = licitacion.organismo
        response.organismo_nombre = org.nombre
        response.organismo_rut = org.rut
        response.organismo_region = org.region
        response.organismo_comuna = org.comuna
        response.organismo_direccion = org.direccion
        response.organismo_ministerio = org.ministerio

    # Solo persistir en cache cuando el detalle está completo
    if licitacion.detalle_sincronizado_at is not None:
        await cache.set(cache_key, response.model_dump_json(), ex=_CACHE_TTL_DETALLE)

    return response
