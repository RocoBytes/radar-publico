"""Endpoints REST de catálogos públicos (sin autenticación).

GET /api/v1/catalogos/regiones  — lista las 16 regiones de Chile ordenadas
GET /api/v1/catalogos/unspsc    — segmentos nivel 2 con familias nivel 4 anidadas

Estos datos son de solo lectura, cargados una vez por seed. No requieren auth.
Se cachean en Redis con TTL de 24 horas — el catálogo seed no cambia en runtime.
"""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.api.deps import DbDep
from app.core import cache
from app.models.catalogos import Region, Unspsc

router = APIRouter(prefix="/catalogos", tags=["catalogos"])

_TTL_CATALOGOS = 86400  # 24 h — seed inmutable en runtime


# ─── Schemas de respuesta ───────────────────────────────────────────────────


class RegionItem(BaseModel):
    """Ítem mínimo de región para el wizard de onboarding."""

    model_config = ConfigDict(from_attributes=True)

    codigo: str
    nombre: str


class RegionesResponse(BaseModel):
    """Lista de regiones ordenadas por campo orden."""

    items: list[RegionItem]


class UnspscFamiliaItem(BaseModel):
    """Familia UNSPSC (nivel 4) anidada dentro de un segmento."""

    model_config = ConfigDict(from_attributes=True)

    codigo: str
    nombre: str


class UnspscSegmentoItem(BaseModel):
    """Segmento UNSPSC (nivel 2) con sus familias."""

    codigo: str
    nombre: str
    familias: list[UnspscFamiliaItem]


class UnspscResponse(BaseModel):
    """Árbol UNSPSC de dos niveles: segmento → familias."""

    items: list[UnspscSegmentoItem]


# ─── Helpers de carga desde BD ──────────────────────────────────────────────


async def _load_regiones(db: DbDep) -> RegionesResponse:
    result = await db.execute(select(Region).order_by(Region.orden))
    regiones = list(result.scalars().all())
    return RegionesResponse(items=[RegionItem.model_validate(r) for r in regiones])


async def _load_unspsc(db: DbDep) -> UnspscResponse:
    segmentos_result = await db.execute(
        select(Unspsc).where(Unspsc.nivel == 2).order_by(Unspsc.codigo)
    )
    segmentos = list(segmentos_result.scalars().all())

    familias_result = await db.execute(
        select(Unspsc).where(Unspsc.nivel == 4).order_by(Unspsc.codigo)
    )
    familias = list(familias_result.scalars().all())

    familias_por_segmento: dict[str, list[UnspscFamiliaItem]] = {}
    for familia in familias:
        seg_codigo = familia.codigo[:2]
        familias_por_segmento.setdefault(seg_codigo, []).append(
            UnspscFamiliaItem(codigo=familia.codigo, nombre=familia.nombre_es)
        )

    items = [
        UnspscSegmentoItem(
            codigo=seg.codigo,
            nombre=seg.nombre_es,
            familias=familias_por_segmento.get(seg.codigo, []),
        )
        for seg in segmentos
    ]
    return UnspscResponse(items=items)


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/regiones", response_model=RegionesResponse)
async def listar_regiones(db: DbDep) -> RegionesResponse:
    """Retorna las 16 regiones de Chile ordenadas por el campo `orden`.

    Sin autenticación — datos públicos de solo lectura.
    Cacheado en Redis 24 h (seed inmutable).
    """
    return await cache.cached(
        "cat:regiones",
        miss=lambda: _load_regiones(db),
        model=RegionesResponse,
        ex=_TTL_CATALOGOS,
    )


@router.get("/unspsc", response_model=UnspscResponse)
async def listar_unspsc(db: DbDep) -> UnspscResponse:
    """Retorna los segmentos UNSPSC (nivel 2) con sus familias (nivel 4) anidadas.

    Sin autenticación — datos públicos de solo lectura.
    Cacheado en Redis 24 h (seed inmutable).
    """
    return await cache.cached(
        "cat:unspsc",
        miss=lambda: _load_unspsc(db),
        model=UnspscResponse,
        ex=_TTL_CATALOGOS,
    )
