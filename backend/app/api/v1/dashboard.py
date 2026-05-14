"""Endpoints REST del dashboard de la empresa.

GET /api/v1/dashboard/resumen   — KPIs + top-5 oportunidades + última sincronización
GET /api/v1/dashboard/segmentos — distribución por segmento UNSPSC
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbDep, EmpresaDep
from app.models.catalogos import Unspsc
from app.models.enums import LicitacionEstado
from app.models.interes import Interes, InteresTipo
from app.models.licitacion import Licitacion, LicitacionItem
from app.models.pipeline import PipelineItem
from app.schemas.dashboard import (
    DashboardResumenResponse,
    DashboardSegmentosResponse,
    LicitacionEnTopResponse,
    SegmentoItem,
    TopOportunidad,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_TOP_N = 5
_VENTANA_CIERRE_HORAS = 24


# ---------------------------------------------------------------------------
# GET /dashboard/resumen
# ---------------------------------------------------------------------------


@router.get("/resumen", response_model=DashboardResumenResponse)
async def obtener_resumen(
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
) -> DashboardResumenResponse:
    """KPIs globales + top-5 oportunidades + última sincronización."""
    ahora = datetime.now(UTC)
    hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)

    # 1. Oportunidades activas (publicadas globales)
    activas_r = await db.execute(
        select(func.count()).select_from(
            select(Licitacion.codigo)
            .where(Licitacion.estado == LicitacionEstado.publicada)
            .subquery()
        )
    )
    oportunidades_activas: int = activas_r.scalar_one()

    # 2. Nuevas hoy (publicadas + fecha_publicacion de hoy UTC)
    nuevas_r = await db.execute(
        select(func.count()).select_from(
            select(Licitacion.codigo)
            .where(
                Licitacion.estado == LicitacionEstado.publicada,
                Licitacion.fecha_publicacion >= hoy_inicio,
            )
            .subquery()
        )
    )
    nuevas_hoy: int = nuevas_r.scalar_one()

    # 3. Próximas a cerrar (fecha_cierre en las próximas 24h)
    ventana_fin = ahora + timedelta(hours=_VENTANA_CIERRE_HORAS)
    proximas_r = await db.execute(
        select(func.count()).select_from(
            select(Licitacion.codigo)
            .where(
                Licitacion.estado == LicitacionEstado.publicada,
                Licitacion.fecha_cierre >= ahora,
                Licitacion.fecha_cierre <= ventana_fin,
            )
            .subquery()
        )
    )
    proximas_a_cerrar: int = proximas_r.scalar_one()

    # 4. En pipeline (cualquier estado)
    pipeline_r = await db.execute(
        select(func.count()).select_from(
            select(PipelineItem.id)
            .where(PipelineItem.empresa_id == empresa.id)
            .subquery()
        )
    )
    en_pipeline: int = pipeline_r.scalar_one()

    # 5. Top-5 por score con licitación y organismo cargados
    top_r = await db.execute(
        select(PipelineItem)
        .where(PipelineItem.empresa_id == empresa.id)
        .order_by(PipelineItem.score.desc().nulls_last())
        .limit(_TOP_N)
        .options(
            selectinload(PipelineItem.licitacion).options(
                selectinload(Licitacion.organismo)
            )
        )
    )
    top_items = list(top_r.scalars().all())

    top_oportunidades = [
        TopOportunidad(
            id=item.id,
            score=item.score,
            estado=item.estado,
            licitacion=LicitacionEnTopResponse(
                codigo=item.licitacion.codigo,
                nombre=item.licitacion.nombre,
                estado=item.licitacion.estado,
                fecha_cierre=item.licitacion.fecha_cierre,
                monto_estimado=item.licitacion.monto_estimado,
                organismo_nombre=(
                    item.licitacion.organismo.nombre
                    if item.licitacion.organismo
                    else None
                ),
            ),
        )
        for item in top_items
    ]

    # 6. Última sincronización = MAX(updated_at) de licitaciones
    sync_r = await db.execute(select(func.max(Licitacion.updated_at)))
    ultima_sincronizacion: datetime | None = sync_r.scalar_one_or_none()

    return DashboardResumenResponse(
        oportunidades_activas=oportunidades_activas,
        nuevas_hoy=nuevas_hoy,
        proximas_a_cerrar=proximas_a_cerrar,
        en_pipeline=en_pipeline,
        top_oportunidades=top_oportunidades,
        ultima_sincronizacion=ultima_sincronizacion,
    )


# ---------------------------------------------------------------------------
# GET /dashboard/segmentos
# ---------------------------------------------------------------------------


@router.get("/segmentos", response_model=DashboardSegmentosResponse)
async def obtener_segmentos(
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
    solo_intereses: bool = Query(default=False),
) -> DashboardSegmentosResponse:
    """Distribución de licitaciones activas por segmento UNSPSC (nivel 2).

    Si solo_intereses=true, filtra solo los segmentos que coinciden con los
    intereses UNSPSC de la empresa.
    """

    # Segmento = primeros 2 dígitos de unspsc_codigo del item
    segmento_col = func.left(LicitacionItem.unspsc_codigo, 2).label("segmento")

    base = (
        select(segmento_col, func.count(LicitacionItem.id).label("cantidad"))
        .join(Licitacion, LicitacionItem.licitacion_codigo == Licitacion.codigo)
        .where(
            Licitacion.estado == LicitacionEstado.publicada,
            LicitacionItem.unspsc_codigo.is_not(None),
        )
        .group_by(segmento_col)
        .order_by(func.count(LicitacionItem.id).desc())
    )

    if solo_intereses:
        # Segmentos donde la empresa tiene intereses UNSPSC
        _tipos_unspsc = [
            InteresTipo.unspsc_segmento,
            InteresTipo.unspsc_familia,
            InteresTipo.unspsc_clase,
            InteresTipo.unspsc_commodity,
        ]
        intereses_r = await db.execute(
            select(Interes.valor).where(
                Interes.empresa_id == empresa.id,
                Interes.tipo.in_(_tipos_unspsc),
            )
        )
        codigos = [row[0] for row in intereses_r.all()]
        if not codigos:
            return DashboardSegmentosResponse(segmentos=[])
        # Primer segmento (2 dígitos) de cada código de interés
        segmentos_interes = {c[:2] for c in codigos}
        base = base.where(
            func.left(LicitacionItem.unspsc_codigo, 2).in_(segmentos_interes)
        )

    rows = (await db.execute(base)).all()

    if not rows:
        return DashboardSegmentosResponse(segmentos=[])

    # Obtener nombres de segmentos del catálogo
    codigos_seg = [row.segmento for row in rows]
    nombres_r = await db.execute(
        select(Unspsc.codigo, Unspsc.nombre_es).where(
            Unspsc.codigo.in_(codigos_seg),
            Unspsc.nivel == 2,
        )
    )
    nombres: dict[str, str] = {row.codigo: row.nombre_es for row in nombres_r.all()}

    segmentos = [
        SegmentoItem(
            codigo=row.segmento,
            nombre=nombres.get(row.segmento, row.segmento),
            cantidad=row.cantidad,
        )
        for row in rows
    ]

    return DashboardSegmentosResponse(segmentos=segmentos)
