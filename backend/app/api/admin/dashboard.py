"""Endpoints del panel admin — dashboard con KPIs y costos de IA.

GET /api/admin/dashboard/kpis        — métricas operacionales globales
GET /api/admin/dashboard/costos-ia   — desglose de costos de IA por empresa
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbDep  # noqa: TCH001
from app.models.empresa import Empresa
from app.models.enums import UserStatus
from app.models.licitacion import Licitacion
from app.models.llm_usage_log import LlmUsageLog
from app.models.usuario import Usuario
from app.schemas.admin_dashboard import (
    AdminCostosIaResponse,
    AdminKpisResponse,
    CostoIaEmpresa,
)

router = APIRouter(prefix="/dashboard", tags=["admin-dashboard"])


@router.get("/kpis", response_model=AdminKpisResponse)
async def obtener_kpis(
    db: DbDep,
    _admin: AdminUser,
) -> AdminKpisResponse:
    """Retorna KPIs operacionales globales para el panel de administración.

    Incluye empresas activas, licitaciones indexadas, mensajes de IA del día
    y costo acumulado de IA en el mes en curso (UTC). Requiere rol admin.
    """
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    mes_inicio = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Empresas activas (usuarios con status=active que tienen empresa asociada)
    empresas_activas: int = (
        await db.execute(
            select(func.count(Empresa.id))
            .join(Usuario, Empresa.usuario_id == Usuario.id)
            .where(Usuario.status == UserStatus.active, Usuario.deleted_at.is_(None))
        )
    ).scalar_one()

    # Total de licitaciones indexadas
    licitaciones_indexadas: int = (
        await db.execute(select(func.count(Licitacion.codigo)))
    ).scalar_one()

    # Mensajes de IA generados hoy (UTC)
    mensajes_ia_hoy: int = (
        await db.execute(
            select(func.count(LlmUsageLog.id)).where(
                LlmUsageLog.created_at >= today_start
            )
        )
    ).scalar_one()

    # Costo de IA acumulado en el mes en curso (UTC)
    costo_raw = (
        await db.execute(
            select(func.coalesce(func.sum(LlmUsageLog.costo_estimado), 0)).where(
                LlmUsageLog.created_at >= mes_inicio
            )
        )
    ).scalar_one()
    costo_ia_mes: float = float(costo_raw or 0)

    return AdminKpisResponse(
        empresas_activas=empresas_activas,
        licitaciones_indexadas=licitaciones_indexadas,
        mensajes_ia_hoy=mensajes_ia_hoy,
        costo_ia_mes=costo_ia_mes,
    )


@router.get("/costos-ia", response_model=AdminCostosIaResponse)
async def obtener_costos_ia(
    db: DbDep,
    _admin: AdminUser,
    meses: int = Query(default=1, ge=1, le=12),
) -> AdminCostosIaResponse:
    """Retorna el desglose de costos de IA por empresa para el período indicado.

    Filtra por los últimos N meses (máx. 12). Solo incluye empresas que
    tengan al menos un registro de uso en el período. Ordena por costo DESC.
    Requiere rol admin.
    """
    fecha_desde = datetime.now(UTC) - timedelta(days=30 * meses)

    stmt = (
        select(
            Empresa.id.label("empresa_id"),
            Empresa.razon_social,
            func.count(LlmUsageLog.id).label("mensajes_mes"),
            func.coalesce(func.sum(LlmUsageLog.tokens_input), 0).label(
                "tokens_input_mes"
            ),
            func.coalesce(func.sum(LlmUsageLog.tokens_output), 0).label(
                "tokens_output_mes"
            ),
            func.coalesce(func.sum(LlmUsageLog.costo_estimado), 0).label("costo_mes"),
        )
        .join(LlmUsageLog, LlmUsageLog.empresa_id == Empresa.id)
        .where(LlmUsageLog.created_at >= fecha_desde)
        .group_by(Empresa.id, Empresa.razon_social)
        .order_by(func.coalesce(func.sum(LlmUsageLog.costo_estimado), 0).desc())
    )

    rows = (await db.execute(stmt)).all()

    empresas: list[CostoIaEmpresa] = [
        CostoIaEmpresa(
            empresa_id=uuid.UUID(str(row.empresa_id)),
            razon_social=row.razon_social,
            mensajes_mes=int(row.mensajes_mes),
            tokens_input_mes=int(row.tokens_input_mes),
            tokens_output_mes=int(row.tokens_output_mes),
            costo_mes=float(row.costo_mes),
        )
        for row in rows
    ]

    return AdminCostosIaResponse(meses=meses, empresas=empresas)
