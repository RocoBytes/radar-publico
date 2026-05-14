"""Servicio de scoring de relevancia licitación-empresa.

Calcula qué tan relevante es una licitación para el perfil comercial de
una empresa, combinando cuatro componentes:

  UNSPSC   40 pts  — coincidencia de rubros (commodity > clase > familia > segmento)
  Región   20 pts  — el organismo opera en alguna de las regiones de la empresa
  Keywords 25 pts  — los términos clave aparecen en el texto de la licitación
  Semántico 15 pts — similitud coseno entre el embedding de la licitación
                     y los embeddings de los intereses de la empresa

La función principal `calcular_score` es síncrona (puro cómputo, sin I/O).
El caller es responsable de cargar todas las relaciones necesarias antes de
invocarla (licitacion.items, licitacion.organismo, empresa.intereses).

Degradación:
  - Sin UNSPSC configurado o sin ítems en la licitación → 0/40
  - Sin regiones configuradas (empresa nacional) → 20/20 (beneficio de la duda)
  - Sin keywords configurados → 0/25
  - Sin embeddings → 0/15
"""

import math
from typing import Any

from app.models.interes import Interes, InteresTipo
from app.models.licitacion import Licitacion, LicitacionItem

_PESO_UNSPSC = 40
_PESO_REGION = 20
_PESO_KEYWORDS = 25
_PESO_SEMANTICO = 15

# Mapa nivel (longitud del código) → puntos máximos
_PUNTOS_POR_NIVEL: dict[int, int] = {
    8: 40,  # commodity
    6: 30,  # clase
    4: 20,  # familia
    2: 10,  # segmento
}

_TIPOS_UNSPSC = frozenset(
    {
        InteresTipo.unspsc_commodity,
        InteresTipo.unspsc_clase,
        InteresTipo.unspsc_familia,
        InteresTipo.unspsc_segmento,
    }
)


def _coseno(a: Any, b: Any) -> float:
    """Similitud coseno entre dos vectores (list, ndarray o similar)."""
    fa = [float(x) for x in a]
    fb = [float(x) for x in b]
    dot = sum(x * y for x, y in zip(fa, fb, strict=False))
    norm_a = math.sqrt(sum(x * x for x in fa))
    norm_b = math.sqrt(sum(x * x for x in fb))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _comp_unspsc(
    intereses: list[Interes],
    items: list[LicitacionItem],
) -> tuple[int, list[dict[str, Any]]]:
    """Componente UNSPSC (0-40 pts). Toma el mejor match entre todos los pares."""
    intereses_unspsc = [i for i in intereses if i.tipo in _TIPOS_UNSPSC]
    if not intereses_unspsc or not items:
        return 0, []

    mejor = 0
    matches: list[dict[str, Any]] = []

    for interes in intereses_unspsc:
        codigo = interes.valor
        nivel = len(codigo)
        pts = _PUNTOS_POR_NIVEL.get(nivel, 0)
        if pts <= mejor:
            continue
        for item in items:
            if item.unspsc_codigo and item.unspsc_codigo.startswith(codigo):
                mejor = pts
                matches = [
                    {
                        "codigo_interes": codigo,
                        "nivel": nivel,
                        "codigo_item": item.unspsc_codigo,
                    }
                ]
                break  # un item alcanza; seguir con otros intereses

    return mejor, matches


def _comp_region(
    regiones_empresa: list[str],
    region_organismo: str | None,
) -> tuple[int, str]:
    """Componente region (0-20 pts).

    - Sin regiones configuradas (empresa nacional) -> 20 pts (sin restriccion)
    - Organismo sin region -> 10 pts (neutral, sin datos suficientes)
    - Match -> 20 pts / No match -> 0 pts
    """
    if not regiones_empresa:
        return _PESO_REGION, "nacional"
    if not region_organismo:
        return _PESO_REGION // 2, "sin_datos"
    region_norm = region_organismo.lower().strip()
    for region in regiones_empresa:
        if region.lower().strip() == region_norm:
            return _PESO_REGION, "match"
    return 0, "no_match"


def _comp_keywords(
    intereses: list[Interes],
    texto: str,
) -> tuple[int, list[str]]:
    """Componente keywords (0-25 pts). Scoring ponderado por prioridad."""
    keywords = [i for i in intereses if i.tipo == InteresTipo.keyword]
    if not keywords:
        return 0, []

    texto_lower = texto.lower()
    peso_total = sum(i.prioridad for i in keywords)
    if peso_total == 0:
        return 0, []

    peso_match = 0
    matched: list[str] = []
    for kw in keywords:
        if kw.valor.lower() in texto_lower:
            peso_match += kw.prioridad
            matched.append(kw.valor)

    puntos = round((peso_match / peso_total) * _PESO_KEYWORDS)
    return min(_PESO_KEYWORDS, puntos), matched


def _comp_semantico(
    embedding_licitacion: Any | None,
    intereses: list[Interes],
) -> tuple[int, float | None]:
    """Componente semantico (0-15 pts). Similitud coseno maxima.

    Umbral de mapeo:
      similitud >= 0.8  -> 15 pts
      0.5 <= sim < 0.8  -> proporcional entre 0 y 15
      sim < 0.5         -> 0 pts
    """
    if embedding_licitacion is None:
        return 0, None

    embeddings_interes = [i.embedding for i in intereses if i.embedding is not None]
    if not embeddings_interes:
        return 0, None

    max_sim = max(_coseno(embedding_licitacion, emb) for emb in embeddings_interes)

    if max_sim >= 0.8:
        puntos = _PESO_SEMANTICO
    elif max_sim >= 0.5:
        puntos = round((max_sim - 0.5) / 0.3 * _PESO_SEMANTICO)
    else:
        puntos = 0

    return min(_PESO_SEMANTICO, puntos), round(max_sim, 4)


def calcular_score(
    licitacion: Licitacion,
    intereses: list[Interes],
    regiones_empresa: list[str],
) -> tuple[int, dict[str, Any]]:
    """Calcula la relevancia de una licitación para una empresa.

    PRE-CONDICIÓN: licitacion.items y licitacion.organismo deben estar
    cargados (selectinload / joinedload) antes de llamar esta función.

    Args:
        licitacion: Licitación con relaciones items y organismo precargadas.
        intereses:  Lista de Interes de la empresa (UNSPSC + keywords).
        regiones_empresa: Lista de nombres de regiones de la empresa.

    Returns:
        Tuple (score 0-100, justificacion dict para score_justificacion JSONB).
    """
    texto = " ".join(filter(None, [licitacion.nombre, licitacion.descripcion]))
    region_organismo = licitacion.organismo.region if licitacion.organismo else None

    pts_u, matches_u = _comp_unspsc(intereses, list(licitacion.items))
    pts_r, razon_r = _comp_region(regiones_empresa, region_organismo)
    pts_k, matches_k = _comp_keywords(intereses, texto)
    pts_s, similitud = _comp_semantico(licitacion.embedding, intereses)

    total = min(100, max(0, pts_u + pts_r + pts_k + pts_s))

    justificacion: dict[str, Any] = {
        "unspsc": {"puntos": pts_u, "max": _PESO_UNSPSC, "matches": matches_u},
        "region": {"puntos": pts_r, "max": _PESO_REGION, "razon": razon_r},
        "keywords": {"puntos": pts_k, "max": _PESO_KEYWORDS, "matches": matches_k},
        "semantico": {"puntos": pts_s, "max": _PESO_SEMANTICO, "similitud": similitud},
        "total": total,
    }

    return total, justificacion
