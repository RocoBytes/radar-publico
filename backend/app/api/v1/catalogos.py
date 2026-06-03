"""Endpoints REST de catálogos públicos (sin autenticación).

GET /api/v1/catalogos/regiones  — lista las 16 regiones de Chile ordenadas
GET /api/v1/catalogos/unspsc    — segmentos nivel 2 con familias nivel 4 anidadas

Estos datos son de solo lectura, cargados una vez por seed. No requieren auth.
"""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.api.deps import DbDep
from app.models.catalogos import Region, Unspsc

router = APIRouter(prefix="/catalogos", tags=["catalogos"])


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


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/regiones", response_model=RegionesResponse)
async def listar_regiones(db: DbDep) -> RegionesResponse:
    """Retorna las 16 regiones de Chile ordenadas por el campo `orden`.

    Sin autenticación — datos públicos de solo lectura.
    """
    result = await db.execute(select(Region).order_by(Region.orden))
    regiones = list(result.scalars().all())
    return RegionesResponse(
        items=[RegionItem.model_validate(r) for r in regiones]
    )


@router.get("/unspsc", response_model=UnspscResponse)
async def listar_unspsc(db: DbDep) -> UnspscResponse:
    """Retorna los segmentos UNSPSC (nivel 2) con sus familias (nivel 4) anidadas.

    Sin autenticación — datos públicos de solo lectura.
    """
    # Cargamos segmentos y familias en dos queries para evitar un join complejo
    segmentos_result = await db.execute(
        select(Unspsc).where(Unspsc.nivel == 2).order_by(Unspsc.codigo)
    )
    segmentos = list(segmentos_result.scalars().all())

    familias_result = await db.execute(
        select(Unspsc).where(Unspsc.nivel == 4).order_by(Unspsc.codigo)
    )
    familias = list(familias_result.scalars().all())

    # Indexar familias por prefijo de segmento (primeros 2 dígitos)
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
