"""Tests unitarios para services/scoring/relevance.py.

Todos son síncronos — el scoring es puro cómputo sin I/O.
Se usan SimpleNamespace para simular ORM objects sin DB.
"""

from types import SimpleNamespace
from typing import Any

from app.models.interes import InteresTipo
from app.services.scoring.relevance import (
    _comp_keywords,
    _comp_region,
    _comp_semantico,
    _comp_unspsc,
    calcular_score,
)

# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------


def make_interes(tipo: InteresTipo, valor: str, prioridad: int = 5, embedding: Any = None) -> Any:
    return SimpleNamespace(tipo=tipo, valor=valor, prioridad=prioridad, embedding=embedding)


def make_item(unspsc_codigo: str | None) -> Any:
    return SimpleNamespace(unspsc_codigo=unspsc_codigo)


def make_licitacion(
    nombre: str = "Servicio de limpieza",
    descripcion: str | None = None,
    items: list[Any] | None = None,
    organismo_region: str | None = None,
    embedding: Any = None,
) -> Any:
    organismo = SimpleNamespace(region=organismo_region) if organismo_region is not None else None
    return SimpleNamespace(
        nombre=nombre,
        descripcion=descripcion,
        items=items or [],
        organismo=organismo,
        embedding=embedding,
    )


# ---------------------------------------------------------------------------
# _comp_unspsc
# ---------------------------------------------------------------------------


class TestCompUnspsc:
    def test_sin_intereses_retorna_cero(self) -> None:
        pts, _ = _comp_unspsc([], [make_item("73101500")])
        assert pts == 0

    def test_sin_items_retorna_cero(self) -> None:
        intereses = [make_interes(InteresTipo.unspsc_segmento, "73")]
        pts, _ = _comp_unspsc(intereses, [])
        assert pts == 0

    def test_match_commodity_da_40(self) -> None:
        intereses = [make_interes(InteresTipo.unspsc_commodity, "73101500")]
        items = [make_item("73101500")]
        pts, matches = _comp_unspsc(intereses, items)
        assert pts == 40
        assert matches[0]["nivel"] == 8

    def test_match_clase_da_30(self) -> None:
        intereses = [make_interes(InteresTipo.unspsc_clase, "731015")]
        items = [make_item("73101500")]
        pts, _ = _comp_unspsc(intereses, items)
        assert pts == 30

    def test_match_familia_da_20(self) -> None:
        intereses = [make_interes(InteresTipo.unspsc_familia, "7310")]
        items = [make_item("73101500")]
        pts, _ = _comp_unspsc(intereses, items)
        assert pts == 20

    def test_match_segmento_da_10(self) -> None:
        intereses = [make_interes(InteresTipo.unspsc_segmento, "73")]
        items = [make_item("73101500")]
        pts, _ = _comp_unspsc(intereses, items)
        assert pts == 10

    def test_toma_mejor_match(self) -> None:
        intereses = [
            make_interes(InteresTipo.unspsc_segmento, "73"),
            make_interes(InteresTipo.unspsc_clase, "731015"),
        ]
        items = [make_item("73101500")]
        pts, _ = _comp_unspsc(intereses, items)
        assert pts == 30

    def test_no_match_retorna_cero(self) -> None:
        intereses = [make_interes(InteresTipo.unspsc_segmento, "80")]
        items = [make_item("73101500")]
        pts, _ = _comp_unspsc(intereses, items)
        assert pts == 0

    def test_item_sin_unspsc_ignorado(self) -> None:
        intereses = [make_interes(InteresTipo.unspsc_segmento, "73")]
        items = [make_item(None)]
        pts, _ = _comp_unspsc(intereses, items)
        assert pts == 0


# ---------------------------------------------------------------------------
# _comp_region
# ---------------------------------------------------------------------------


class TestCompRegion:
    def test_empresa_sin_regiones_es_nacional(self) -> None:
        pts, razon = _comp_region([], "Metropolitana de Santiago")
        assert pts == 20
        assert razon == "nacional"

    def test_organismo_sin_region_neutral(self) -> None:
        pts, razon = _comp_region(["Metropolitana de Santiago"], None)
        assert pts == 10
        assert razon == "sin_datos"

    def test_match_exacto_da_20(self) -> None:
        pts, razon = _comp_region(["Metropolitana de Santiago"], "Metropolitana de Santiago")
        assert pts == 20
        assert razon == "match"

    def test_match_case_insensitive(self) -> None:
        pts, razon = _comp_region(["metropolitana de santiago"], "Metropolitana de Santiago")
        assert pts == 20
        assert razon == "match"

    def test_no_match_da_cero(self) -> None:
        pts, razon = _comp_region(["Valparaíso"], "Metropolitana de Santiago")
        assert pts == 0
        assert razon == "no_match"


# ---------------------------------------------------------------------------
# _comp_keywords
# ---------------------------------------------------------------------------


class TestCompKeywords:
    def test_sin_keywords_retorna_cero(self) -> None:
        intereses = [make_interes(InteresTipo.unspsc_segmento, "73")]
        pts, _ = _comp_keywords(intereses, "limpieza de oficinas")
        assert pts == 0

    def test_keyword_presente_proporcional(self) -> None:
        intereses = [
            make_interes(InteresTipo.keyword, "limpieza", prioridad=5),
            make_interes(InteresTipo.keyword, "aseo", prioridad=5),
        ]
        pts, matched = _comp_keywords(intereses, "Servicio de limpieza industrial")
        # 5/10 * 25 = 12 pts
        assert pts == 12 or pts == 13  # redondeo
        assert "limpieza" in matched
        assert "aseo" not in matched

    def test_todos_los_keywords_presentes(self) -> None:
        intereses = [
            make_interes(InteresTipo.keyword, "limpieza", prioridad=5),
            make_interes(InteresTipo.keyword, "aseo", prioridad=5),
        ]
        pts, matched = _comp_keywords(intereses, "limpieza y aseo de oficinas")
        assert pts == 25
        assert len(matched) == 2

    def test_keyword_case_insensitive(self) -> None:
        intereses = [make_interes(InteresTipo.keyword, "LIMPIEZA", prioridad=10)]
        pts, _ = _comp_keywords(intereses, "servicio de limpieza")
        assert pts == 25

    def test_prioridad_pesa_en_score(self) -> None:
        intereses = [
            make_interes(InteresTipo.keyword, "limpieza", prioridad=8),
            make_interes(InteresTipo.keyword, "aseo", prioridad=2),
        ]
        pts_sin_aseo, _ = _comp_keywords(intereses, "limpieza industrial")
        pts_ambos, _ = _comp_keywords(intereses, "limpieza y aseo")
        assert pts_ambos > pts_sin_aseo


# ---------------------------------------------------------------------------
# _comp_semantico
# ---------------------------------------------------------------------------


class TestCompSemantico:
    def test_sin_embedding_licitacion_retorna_cero(self) -> None:
        intereses = [make_interes(InteresTipo.keyword, "x", embedding=[0.1] * 1024)]
        pts, sim = _comp_semantico(None, intereses)
        assert pts == 0
        assert sim is None

    def test_sin_embeddings_intereses_retorna_cero(self) -> None:
        intereses = [make_interes(InteresTipo.keyword, "x", embedding=None)]
        pts, sim = _comp_semantico([0.1] * 1024, intereses)
        assert pts == 0
        assert sim is None

    def test_alta_similitud_da_15(self) -> None:
        vec = [1.0] + [0.0] * 1023
        intereses = [make_interes(InteresTipo.keyword, "x", embedding=vec)]
        pts, sim = _comp_semantico(vec, intereses)
        assert pts == 15
        assert sim is not None and sim >= 0.99

    def test_similitud_media_da_puntos_proporcionales(self) -> None:
        # Construir dos vectores con similitud ~0.65
        import math

        # vec_a perpendicular a vec_b + componente compartida para sim ≈ 0.65
        vec_a = [math.cos(0.863)] + [math.sin(0.863)] + [0.0] * 1022
        vec_b = [1.0] + [0.0] * 1023
        intereses = [make_interes(InteresTipo.keyword, "x", embedding=vec_b)]
        pts, sim = _comp_semantico(vec_a, intereses)
        assert sim is not None and 0.5 <= sim <= 0.8
        assert 0 < pts < 15

    def test_similitud_baja_da_cero(self) -> None:
        # Vectores perpendiculares → similitud 0
        vec_a = [1.0] + [0.0] * 1023
        vec_b = [0.0, 1.0] + [0.0] * 1022
        intereses = [make_interes(InteresTipo.keyword, "x", embedding=vec_b)]
        pts, sim = _comp_semantico(vec_a, intereses)
        assert pts == 0


# ---------------------------------------------------------------------------
# calcular_score (integración de componentes)
# ---------------------------------------------------------------------------


class TestCalcularScore:
    def test_score_maximo_con_todo_configurado(self) -> None:
        vec = [1.0] + [0.0] * 1023
        # Ambas keywords aparecen en el texto → keywords=25
        intereses = [
            make_interes(InteresTipo.unspsc_commodity, "73101500"),
            make_interes(InteresTipo.keyword, "limpieza", prioridad=5),
            make_interes(InteresTipo.keyword, "industrial", prioridad=5, embedding=vec),
        ]
        licitacion = make_licitacion(
            nombre="limpieza industrial",
            items=[make_item("73101500")],
            organismo_region="Metropolitana de Santiago",
            embedding=vec,
        )
        score, just = calcular_score(licitacion, intereses, ["Metropolitana de Santiago"])
        assert score == 100
        assert just["total"] == 100
        assert just["unspsc"]["puntos"] == 40
        assert just["region"]["puntos"] == 20
        assert just["keywords"]["puntos"] == 25
        assert just["semantico"]["puntos"] == 15

    def test_empresa_sin_perfil_score_bajo(self) -> None:
        licitacion = make_licitacion(items=[make_item("73101500")])
        score, _ = calcular_score(licitacion, [], [])
        # Sin intereses, solo puntúa región (nacional = 20)
        assert score == 20

    def test_score_entre_0_y_100(self) -> None:
        licitacion = make_licitacion()
        score, _ = calcular_score(licitacion, [], [])
        assert 0 <= score <= 100

    def test_justificacion_contiene_todas_las_claves(self) -> None:
        licitacion = make_licitacion()
        _, just = calcular_score(licitacion, [], [])
        for key in ("unspsc", "region", "keywords", "semantico", "total"):
            assert key in just

    def test_organismo_none_no_rompe(self) -> None:
        # Empresa con regiones + organismo None → "sin_datos" → 10 pts
        licitacion = SimpleNamespace(
            nombre="Test",
            descripcion=None,
            items=[],
            organismo=None,
            embedding=None,
        )
        score, just = calcular_score(licitacion, [], ["Valparaíso"])
        assert just["region"]["razon"] == "sin_datos"
        assert score == 10
