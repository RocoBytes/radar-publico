"""Endpoints REST del módulo de Futuro.

GET /api/v1/futuro/renovaciones — feed de licitaciones adjudicadas renovables
  filtradas por los intereses UNSPSC de la empresa, ordenadas por
  fecha_estimada_termino_contrato ASC.

GET /api/v1/futuro/plan-anual — líneas del plan anual de compras de organismos
  filtradas por los intereses UNSPSC de la empresa.

Implementa Epic 9 de docs/spec.md.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import exists, func, or_, select

from app.api.deps import CurrentUser, DbDep, EmpresaDep
from app.models.enums import LicitacionEstado
from app.models.interes import Interes, InteresTipo
from app.models.licitacion import Licitacion, LicitacionItem
from app.models.organismo import Organismo
from app.models.plan_anual import PlanAnualLinea
from app.schemas.futuro import (
    PlanAnualLineaResponse,
    PlanAnualListResponse,
    RenovacionesListResponse,
    RenovacionResponse,
)

router = APIRouter(prefix="/futuro", tags=["futuro"])

_TIPOS_UNSPSC = [
    InteresTipo.unspsc_segmento,
    InteresTipo.unspsc_familia,
    InteresTipo.unspsc_clase,
    InteresTipo.unspsc_commodity,
]


@router.get("/renovaciones", response_model=RenovacionesListResponse)
async def listar_renovaciones(
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    meses_horizonte: int = Query(
        default=24,
        ge=1,
        le=60,
        description="Solo muestra contratos que terminan dentro de este horizonte (meses).",
    ),
) -> RenovacionesListResponse:
    """Feed de licitaciones adjudicadas con renovación próxima.

    Filtra por los intereses UNSPSC de la empresa (prefijo). Si la empresa
    no tiene intereses UNSPSC configurados, retorna todas las renovables
    dentro del horizonte.
    """
    ahora = datetime.now(UTC)
    horizonte_dt = ahora + timedelta(days=meses_horizonte * 30)

    # 1. Intereses UNSPSC de la empresa (prefijos para LIKE)
    intereses_r = await db.execute(
        select(Interes.valor).where(
            Interes.empresa_id == empresa.id,
            Interes.tipo.in_(_TIPOS_UNSPSC),
        )
    )
    codigos_interes = [row[0] for row in intereses_r.all()]

    # 2. Query base: adjudicadas, renovables, dentro del horizonte temporal
    base_q = (
        select(Licitacion)
        .outerjoin(Organismo, Licitacion.codigo_organismo == Organismo.codigo_organismo)
        .add_columns(Organismo.nombre.label("organismo_nombre"))
        .where(
            Licitacion.es_renovable.is_(True),
            Licitacion.estado == LicitacionEstado.adjudicada,
            or_(
                Licitacion.fecha_estimada_termino_contrato.is_(None),
                Licitacion.fecha_estimada_termino_contrato <= horizonte_dt,
            ),
        )
    )

    # 3. Filtrar por UNSPSC si la empresa tiene intereses configurados
    if codigos_interes:
        item_conditions = [LicitacionItem.unspsc_codigo.like(f"{c}%") for c in codigos_interes]
        base_q = base_q.where(
            exists(
                select(LicitacionItem.id).where(
                    LicitacionItem.licitacion_codigo == Licitacion.codigo,
                    or_(*item_conditions),
                )
            )
        )

    # 4. Total (sin paginación)
    count_q = select(func.count()).select_from(base_q.subquery())
    total: int = (await db.execute(count_q)).scalar_one()

    # 5. Resultado paginado, ordenado por fecha de término ASC (nulls last)
    rows = (
        await db.execute(
            base_q.order_by(Licitacion.fecha_estimada_termino_contrato.asc().nulls_last())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    # 6. Construir items con dias_para_termino calculado en Python
    items = []
    for row in rows:
        lic: Licitacion = row[0]
        organismo_nombre: str | None = row[1]

        dias_para_termino: int | None = None
        if lic.fecha_estimada_termino_contrato is not None:
            delta = lic.fecha_estimada_termino_contrato - ahora
            dias_para_termino = delta.days

        items.append(
            RenovacionResponse(
                licitacion_codigo=lic.codigo,
                nombre=lic.nombre,
                organismo_nombre=organismo_nombre,
                monto_estimado=(
                    float(lic.monto_estimado) if lic.monto_estimado is not None else None
                ),
                fecha_adjudicacion=lic.fecha_adjudicacion,
                duracion_estimada_meses=lic.duracion_estimada_meses,
                fecha_estimada_termino_contrato=lic.fecha_estimada_termino_contrato,
                dias_para_termino=dias_para_termino,
            )
        )

    return RenovacionesListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/plan-anual", response_model=PlanAnualListResponse)
async def listar_plan_anual(
    db: DbDep,
    current_user: CurrentUser,
    empresa: EmpresaDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    ano: int | None = Query(
        default=None, ge=2020, le=2035, description="Año del plan. None = año actual."
    ),
    q: str | None = Query(default=None, max_length=200),
) -> PlanAnualListResponse:
    """Líneas del plan anual de compras filtradas por intereses UNSPSC de la empresa."""
    ano_efectivo = ano if ano is not None else datetime.now().year

    intereses_r = await db.execute(
        select(Interes.valor).where(
            Interes.empresa_id == empresa.id,
            Interes.tipo.in_(_TIPOS_UNSPSC),
        )
    )
    codigos_interes = [row[0] for row in intereses_r.all()]

    base_q = select(PlanAnualLinea).where(PlanAnualLinea.ano == ano_efectivo)

    if codigos_interes:
        base_q = base_q.where(
            or_(*(PlanAnualLinea.unspsc_codigo.like(f"{c}%") for c in codigos_interes))
        )

    if q:
        base_q = base_q.where(PlanAnualLinea.descripcion.ilike(f"%{q}%"))

    count_q = select(func.count()).select_from(base_q.subquery())
    total: int = (await db.execute(count_q)).scalar_one()

    rows = (
        (
            await db.execute(
                base_q.order_by(PlanAnualLinea.monto_estimado.desc().nulls_last())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    items = [
        PlanAnualLineaResponse(
            id=row.id,
            ano=row.ano,
            codigo_organismo=row.codigo_organismo,
            descripcion=row.descripcion,
            unspsc_codigo=row.unspsc_codigo,
            unspsc_nombre=row.unspsc_nombre,
            monto_estimado=float(row.monto_estimado) if row.monto_estimado is not None else None,
            moneda=row.moneda or "CLP",
            mes_estimado=row.mes_estimado,
            modalidad=row.modalidad,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            licitacion_codigo=row.licitacion_codigo,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return PlanAnualListResponse(total=total, page=page, page_size=page_size, items=items)
