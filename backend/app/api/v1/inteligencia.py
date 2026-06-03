"""Endpoints de inteligencia de mercado para licitaciones.

GET /api/v1/licitaciones/{codigo}/inteligencia — contexto histórico del organismo
comprador: volumen, montos y top proveedores adjudicados en los últimos 2 años.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep  # noqa: TCH001
from app.models.adjudicacion import Adjudicacion
from app.models.licitacion import Licitacion, LicitacionItem
from app.models.organismo import Organismo
from app.models.proveedor import Proveedor
from app.schemas.inteligencia import InteligenciaResponse, TopProveedor

router = APIRouter(prefix="/licitaciones", tags=["inteligencia"])

# Ventana histórica para análisis de mercado
_VENTANA_DIAS: int = 730


@router.get("/{codigo}/inteligencia", response_model=InteligenciaResponse)
async def obtener_inteligencia(
    codigo: str,
    db: DbDep,
    _current_user: CurrentUser,
) -> InteligenciaResponse:
    """Retorna contexto histórico del organismo comprador para una licitación.

    Incluye total de licitaciones, monto promedio y top 5 proveedores
    adjudicados en los últimos 2 años. Requiere usuario autenticado.
    Levanta 404 si el código no existe.
    """
    # 1. Obtener la licitación
    licitacion: Licitacion | None = (
        await db.execute(select(Licitacion).where(Licitacion.codigo == codigo))
    ).scalar_one_or_none()

    if licitacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Licitación '{codigo}' no encontrada",
        )

    # Si no tiene organismo asociado, retornamos valores vacíos
    if licitacion.codigo_organismo is None:
        return InteligenciaResponse(
            organismo_nombre=None,
            total_licitaciones_organismo=0,
            monto_promedio_organismo=None,
            top_proveedores=[],
            proveedores_unicos_organismo=0,
            precio_min_organismo=None,
            precio_max_organismo=None,
            top_competidores_rubro=[],
        )

    fecha_limite = datetime.now(UTC) - timedelta(days=_VENTANA_DIAS)

    # 2. Nombre del organismo
    organismo: Organismo | None = (
        await db.execute(
            select(Organismo).where(Organismo.codigo_organismo == licitacion.codigo_organismo)
        )
    ).scalar_one_or_none()
    organismo_nombre = organismo.nombre if organismo is not None else None

    # 3. Estadísticas de licitaciones del organismo en los últimos 2 años
    stats_stmt = select(
        func.count(Licitacion.codigo).label("total"),
        func.avg(Licitacion.monto_estimado).label("avg_monto"),
        func.sum(Licitacion.monto_estimado).label("sum_monto"),
    ).where(
        Licitacion.codigo_organismo == licitacion.codigo_organismo,
        Licitacion.codigo != codigo,
        Licitacion.fecha_publicacion >= fecha_limite,
        Licitacion.monto_estimado.is_not(None),
    )
    stats_row = (await db.execute(stats_stmt)).one()

    total_licitaciones: int = int(stats_row.total or 0)
    monto_promedio: float | None = (
        float(stats_row.avg_monto) if stats_row.avg_monto is not None else None
    )

    # 4. Top 5 proveedores por adjudicaciones en el organismo (últimos 2 años)
    top_stmt = (
        select(
            Proveedor.rut,
            Proveedor.razon_social,
            func.count(Adjudicacion.id).label("licitaciones_ganadas"),
            func.sum(Adjudicacion.monto_adjudicado).label("monto_total"),
        )
        .join(Adjudicacion, Adjudicacion.rut_proveedor == Proveedor.rut)
        .join(Licitacion, Adjudicacion.licitacion_codigo == Licitacion.codigo)
        .where(
            Licitacion.codigo_organismo == licitacion.codigo_organismo,
            Adjudicacion.fecha_adjudicacion >= fecha_limite,
        )
        .group_by(Proveedor.rut, Proveedor.razon_social)
        .order_by(func.count(Adjudicacion.id).desc())
        .limit(5)
    )
    top_rows = (await db.execute(top_stmt)).all()

    top_proveedores: list[TopProveedor] = [
        TopProveedor(
            rut=row.rut,
            razon_social=row.razon_social,
            licitaciones_ganadas=int(row.licitaciones_ganadas),
            monto_total=float(row.monto_total) if row.monto_total is not None else None,
        )
        for row in top_rows
    ]

    # 5. Precios reales adjudicados + diversidad de proveedores en el organismo
    precios_stmt = (
        select(
            func.min(Adjudicacion.monto_adjudicado).label("precio_min"),
            func.max(Adjudicacion.monto_adjudicado).label("precio_max"),
            func.count(Adjudicacion.rut_proveedor.distinct()).label("proveedores_unicos"),
        )
        .join(Licitacion, Adjudicacion.licitacion_codigo == Licitacion.codigo)
        .where(
            Licitacion.codigo_organismo == licitacion.codigo_organismo,
            Adjudicacion.fecha_adjudicacion >= fecha_limite,
            Adjudicacion.monto_adjudicado.is_not(None),
        )
    )
    precios_row = (await db.execute(precios_stmt)).one()
    precio_min: float | None = (
        float(precios_row.precio_min) if precios_row.precio_min is not None else None
    )
    precio_max: float | None = (
        float(precios_row.precio_max) if precios_row.precio_max is not None else None
    )
    proveedores_unicos: int = int(precios_row.proveedores_unicos or 0)

    # 6. Top competidores en el mismo rubro UNSPSC (últimos 2 años)
    unspsc_de_esta_lic = select(LicitacionItem.unspsc_codigo).where(
        LicitacionItem.licitacion_codigo == codigo,
        LicitacionItem.unspsc_codigo.is_not(None),
    )
    lics_mismo_rubro = (
        select(LicitacionItem.licitacion_codigo)
        .where(
            LicitacionItem.unspsc_codigo.in_(unspsc_de_esta_lic),
            LicitacionItem.licitacion_codigo != codigo,
        )
        .distinct()
    )
    top_rubro_stmt = (
        select(
            Proveedor.rut,
            Proveedor.razon_social,
            func.count(Adjudicacion.licitacion_codigo.distinct()).label("licitaciones_ganadas"),
            func.sum(Adjudicacion.monto_adjudicado).label("monto_total"),
        )
        .join(Adjudicacion, Adjudicacion.rut_proveedor == Proveedor.rut)
        .where(
            Adjudicacion.licitacion_codigo.in_(lics_mismo_rubro),
            Adjudicacion.fecha_adjudicacion >= fecha_limite,
        )
        .group_by(Proveedor.rut, Proveedor.razon_social)
        .order_by(func.count(Adjudicacion.licitacion_codigo.distinct()).desc())
        .limit(5)
    )
    top_rubro_rows = (await db.execute(top_rubro_stmt)).all()
    top_competidores_rubro: list[TopProveedor] = [
        TopProveedor(
            rut=row.rut,
            razon_social=row.razon_social,
            licitaciones_ganadas=int(row.licitaciones_ganadas),
            monto_total=float(row.monto_total) if row.monto_total is not None else None,
        )
        for row in top_rubro_rows
    ]

    return InteligenciaResponse(
        organismo_nombre=organismo_nombre,
        total_licitaciones_organismo=total_licitaciones,
        monto_promedio_organismo=monto_promedio,
        top_proveedores=top_proveedores,
        proveedores_unicos_organismo=proveedores_unicos,
        precio_min_organismo=precio_min,
        precio_max_organismo=precio_max,
        top_competidores_rubro=top_competidores_rubro,
    )
