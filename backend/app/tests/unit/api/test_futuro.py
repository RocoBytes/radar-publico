"""Tests unitarios para GET /api/v1/futuro/renovaciones y GET /api/v1/futuro/plan-anual.

Cubre renovaciones:
- Sin licitaciones renovables → lista vacía.
- Licitación renovable adjudicada → aparece en el feed.
- Filtro por UNSPSC: solo aparece si el item coincide con intereses de la empresa.
- dias_para_termino se calcula correctamente.
- Paginación funciona.

Cubre plan-anual:
- Sin datos → lista vacía.
- Línea del año correcto → aparece con campos esperados.
- Filtro por año excluye otras anualidades.
- Filtro ?q= busca por descripcion (ILIKE).
- Sin token → 401.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.core.security import create_access_token
from app.models.empresa import Empresa
from app.models.enums import LicitacionEstado, PlanAnualStatus, UserRole, UserStatus

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


def _auth(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user_id)}"}


@pytest_asyncio.fixture(autouse=True)
async def _limpieza(db_session: AsyncSession) -> None:  # type: ignore[misc]
    from app.models.interes import Interes
    from app.models.licitacion import Licitacion, LicitacionItem
    from app.models.plan_anual import PlanAnualLinea

    async def _borrar() -> None:
        from app.models.catalogos import Unspsc

        await db_session.execute(
            delete(LicitacionItem).where(LicitacionItem.licitacion_codigo.like("TEST-FUT-%"))
        )
        await db_session.execute(delete(Licitacion).where(Licitacion.codigo.like("TEST-FUT-%")))
        await db_session.execute(delete(Interes).where(Interes.valor.in_(["73", "80"])))
        await db_session.execute(
            delete(PlanAnualLinea).where(PlanAnualLinea.descripcion.like("TEST-PAC%"))
        )
        # Eliminar CUALQUIER item que referencie estos códigos UNSPSC antes de
        # borrar los códigos mismos — previene FK violation por datos residuales
        # de otros módulos de test que usan los mismos códigos UNSPSC.
        await db_session.execute(
            delete(LicitacionItem).where(LicitacionItem.unspsc_codigo.in_(["73101500", "80101500"]))
        )
        await db_session.execute(delete(Unspsc).where(Unspsc.codigo.in_(["73101500", "80101500"])))
        await db_session.commit()

    await _borrar()
    yield  # type: ignore[misc]
    await _borrar()


@pytest_asyncio.fixture
async def empresa_con_usuario(
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> tuple[Any, Empresa]:
    from sqlalchemy import select

    user: Any = await make_user(
        email="futuro_test@example.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        razon_social="Futuro Test SpA",
    )
    result = await db_session.execute(select(Empresa).where(Empresa.usuario_id == user.id))
    empresa: Empresa = result.scalar_one()
    return user, empresa


async def _crear_licitacion_renovable(
    db_session: AsyncSession,
    *,
    codigo: str = "TEST-FUT-001",
    meses: int = 12,
    dias_termino_desde_ahora: int = 90,
    unspsc: str | None = None,
) -> None:
    from app.models.licitacion import Licitacion, LicitacionItem

    ahora = datetime.now(UTC)
    fecha_term = ahora + timedelta(days=dias_termino_desde_ahora)
    fecha_adj = fecha_term - timedelta(days=meses * 30)

    lic = Licitacion(
        codigo=codigo,
        nombre=f"Licitación renovable {codigo}",
        estado=LicitacionEstado.adjudicada,
        es_renovable=True,
        monto_estimado=5_000_000.0,
        duracion_estimada_meses=meses,
        fecha_adjudicacion=fecha_adj,
        fecha_estimada_termino_contrato=fecha_term,
    )
    db_session.add(lic)
    await db_session.flush()

    if unspsc:
        from app.models.catalogos import Unspsc

        existing = await db_session.get(Unspsc, unspsc)
        if existing is None:
            db_session.add(
                Unspsc(
                    codigo=unspsc,
                    nivel=8,
                    segmento=unspsc[:2],
                    nombre_es=f"Código UNSPSC {unspsc} (test)",
                )
            )
            await db_session.flush()

        db_session.add(
            LicitacionItem(
                licitacion_codigo=codigo,
                numero_item=1,
                unspsc_codigo=unspsc,
                nombre_producto="Producto test",
            )
        )

    await db_session.commit()


async def _crear_plan_linea(
    db_session: AsyncSession,
    *,
    ano: int,
    descripcion: str,
    codigo_organismo: int,
    status: PlanAnualStatus = PlanAnualStatus.planificada,
) -> Any:
    """Inserta una PlanAnualLinea directamente en BD y retorna la instancia."""
    from sqlalchemy import select

    from app.models.organismo import Organismo
    from app.models.plan_anual import PlanAnualLinea

    # Crear el organismo si no existe (FK real, no puede ser nulo)
    result = await db_session.execute(
        select(Organismo).where(Organismo.codigo_organismo == codigo_organismo)
    )
    if result.scalar_one_or_none() is None:
        db_session.add(
            Organismo(
                codigo_organismo=codigo_organismo,
                nombre=f"Organismo Test {codigo_organismo}",
            )
        )
        await db_session.flush()

    linea = PlanAnualLinea(
        ano=ano,
        codigo_organismo=codigo_organismo,
        descripcion=descripcion,
        status=status,
    )
    db_session.add(linea)
    await db_session.commit()
    await db_session.refresh(linea)
    return linea


# ---------------------------------------------------------------------------
# Tests — renovaciones
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_renovaciones_vacio(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Empresa],
) -> None:
    """Sin licitaciones renovables → lista vacía."""
    user, _ = empresa_con_usuario
    r = await client.get(
        "/api/v1/futuro/renovaciones",
        headers=_auth(str(user.id)),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_renovaciones_aparece_adjudicada_renovable(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Empresa],
    db_session: AsyncSession,
) -> None:
    """Licitación adjudicada+renovable dentro del horizonte aparece en el feed."""
    user, _ = empresa_con_usuario
    await _crear_licitacion_renovable(
        db_session, codigo="TEST-FUT-001", dias_termino_desde_ahora=60
    )

    r = await client.get(
        "/api/v1/futuro/renovaciones",
        headers=_auth(str(user.id)),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["licitacion_codigo"] == "TEST-FUT-001"
    assert item["dias_para_termino"] is not None
    assert 55 <= item["dias_para_termino"] <= 65


@pytest.mark.asyncio
async def test_renovaciones_no_incluye_publicada(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Empresa],
    db_session: AsyncSession,
) -> None:
    """Licitación publicada (no adjudicada) no aparece en renovaciones."""
    from app.models.licitacion import Licitacion

    user, _ = empresa_con_usuario

    lic_pub = Licitacion(
        codigo="TEST-FUT-002",
        nombre="Publicada no renovable",
        estado=LicitacionEstado.publicada,
        es_renovable=True,
        fecha_estimada_termino_contrato=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(lic_pub)
    await db_session.commit()

    r = await client.get(
        "/api/v1/futuro/renovaciones",
        headers=_auth(str(user.id)),
    )
    assert r.status_code == 200
    codigos = [i["licitacion_codigo"] for i in r.json()["items"]]
    assert "TEST-FUT-002" not in codigos


@pytest.mark.asyncio
async def test_renovaciones_filtro_unspsc(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Empresa],
    db_session: AsyncSession,
) -> None:
    """Si empresa tiene intereses UNSPSC, solo aparecen licitaciones que coinciden.

    Usamos códigos existentes en el catálogo seed: 73101500 y 80101500.
    Interés de la empresa: segmento "73". Solo la licitación con item "73101500" debe aparecer.
    """
    from app.models.interes import Interes, InteresTipo

    user, empresa = empresa_con_usuario

    # Interés: segmento "73" (existe en el catálogo seed)
    interes = Interes(
        empresa_id=empresa.id,
        tipo=InteresTipo.unspsc_segmento,
        valor="73",
    )
    db_session.add(interes)
    await db_session.commit()

    # Licitación con item en segmento "73" → debe aparecer (FK válida: 73101500 existe)
    await _crear_licitacion_renovable(db_session, codigo="TEST-FUT-003", unspsc="73101500")
    # Licitación con item en segmento "80" → no debe aparecer (FK válida: 80101500 existe)
    await _crear_licitacion_renovable(db_session, codigo="TEST-FUT-004", unspsc="80101500")

    r = await client.get(
        "/api/v1/futuro/renovaciones",
        headers=_auth(str(user.id)),
    )
    assert r.status_code == 200
    codigos = {i["licitacion_codigo"] for i in r.json()["items"]}
    assert "TEST-FUT-003" in codigos
    assert "TEST-FUT-004" not in codigos


@pytest.mark.asyncio
async def test_renovaciones_paginacion(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Empresa],
    db_session: AsyncSession,
) -> None:
    """Paginación funciona correctamente."""
    user, _ = empresa_con_usuario

    for i in range(5):
        await _crear_licitacion_renovable(
            db_session,
            codigo=f"TEST-FUT-{100 + i}",
            dias_termino_desde_ahora=30 + i * 10,
        )

    r1 = await client.get(
        "/api/v1/futuro/renovaciones?page=1&page_size=3",
        headers=_auth(str(user.id)),
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["total"] == 5
    assert len(d1["items"]) == 3
    assert d1["page"] == 1
    assert d1["page_size"] == 3

    r2 = await client.get(
        "/api/v1/futuro/renovaciones?page=2&page_size=3",
        headers=_auth(str(user.id)),
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert len(d2["items"]) == 2


@pytest.mark.asyncio
async def test_renovaciones_horizonte_excluye_lejanos(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Empresa],
    db_session: AsyncSession,
) -> None:
    """Licitaciones cuyo término está más allá del horizonte no aparecen."""
    user, _ = empresa_con_usuario

    # Termina en 5 meses → dentro del horizonte de 6 meses
    await _crear_licitacion_renovable(
        db_session, codigo="TEST-FUT-CERCA", dias_termino_desde_ahora=150
    )
    # Termina en 25 meses → fuera del horizonte de 24 meses (default)
    await _crear_licitacion_renovable(
        db_session, codigo="TEST-FUT-LEJOS", dias_termino_desde_ahora=760
    )

    r = await client.get(
        "/api/v1/futuro/renovaciones",
        headers=_auth(str(user.id)),
    )
    codigos = {i["licitacion_codigo"] for i in r.json()["items"]}
    assert "TEST-FUT-CERCA" in codigos
    assert "TEST-FUT-LEJOS" not in codigos


# ---------------------------------------------------------------------------
# Tests — plan-anual
# ---------------------------------------------------------------------------

# Código de organismo ficticio para tests de plan anual. Se crea en BD si no existe.
_ORGANISMO_PAC = 99999


@pytest.mark.asyncio
async def test_plan_anual_lista_vacia(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Empresa],
) -> None:
    """Sin líneas de plan anual → 200, total=0, items=[]."""
    user, _ = empresa_con_usuario
    r = await client.get(
        "/api/v1/futuro/plan-anual",
        headers=_auth(str(user.id)),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_plan_anual_aparece_linea_del_ano(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Empresa],
    db_session: AsyncSession,
) -> None:
    """Línea con ano=2025 → aparece al pedir ?ano=2025 con campos requeridos."""
    user, _ = empresa_con_usuario

    await _crear_plan_linea(
        db_session,
        ano=2025,
        descripcion="TEST-PAC Servicio de consultoría 2025",
        codigo_organismo=_ORGANISMO_PAC,
    )

    r = await client.get(
        "/api/v1/futuro/plan-anual?ano=2025",
        headers=_auth(str(user.id)),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    item = next(
        (i for i in data["items"] if "TEST-PAC" in i.get("descripcion", "")),
        None,
    )
    assert item is not None, "La línea TEST-PAC no aparece en la respuesta"
    assert item["ano"] == 2025
    assert "id" in item
    assert "descripcion" in item
    assert "status" in item


@pytest.mark.asyncio
async def test_plan_anual_filtro_ano_excluye_otro_ano(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Empresa],
    db_session: AsyncSession,
) -> None:
    """Línea 2024 y línea 2025 → ?ano=2025 solo retorna la de 2025."""
    user, _ = empresa_con_usuario

    await _crear_plan_linea(
        db_session,
        ano=2024,
        descripcion="TEST-PAC Linea ano 2024",
        codigo_organismo=_ORGANISMO_PAC,
    )
    await _crear_plan_linea(
        db_session,
        ano=2025,
        descripcion="TEST-PAC Linea ano 2025",
        codigo_organismo=_ORGANISMO_PAC,
    )

    r = await client.get(
        "/api/v1/futuro/plan-anual?ano=2025",
        headers=_auth(str(user.id)),
    )
    assert r.status_code == 200
    data = r.json()

    descripciones = [i["descripcion"] for i in data["items"]]
    assert any("TEST-PAC Linea ano 2025" in d for d in descripciones)
    assert all("TEST-PAC Linea ano 2024" not in d for d in descripciones)


@pytest.mark.asyncio
async def test_plan_anual_filtro_q(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Empresa],
    db_session: AsyncSession,
) -> None:
    """Filtro ?q= busca por descripcion: coincidencia aparece, no-coincidencia no aparece."""
    user, _ = empresa_con_usuario

    await _crear_plan_linea(
        db_session,
        ano=2025,
        descripcion="TEST-PAC Servicios de limpieza industrial",
        codigo_organismo=_ORGANISMO_PAC,
    )

    # Búsqueda que sí coincide
    r_match = await client.get(
        "/api/v1/futuro/plan-anual?ano=2025&q=limpieza",
        headers=_auth(str(user.id)),
    )
    assert r_match.status_code == 200
    descripciones_match = [i["descripcion"] for i in r_match.json()["items"]]
    assert any(
        "limpieza" in d.lower() for d in descripciones_match
    ), "El filtro q=limpieza debería retornar la línea de limpieza"

    # Búsqueda que NO coincide
    r_no_match = await client.get(
        "/api/v1/futuro/plan-anual?ano=2025&q=tecnologia",
        headers=_auth(str(user.id)),
    )
    assert r_no_match.status_code == 200
    descripciones_no_match = [i["descripcion"] for i in r_no_match.json()["items"]]
    assert not any(
        "TEST-PAC Servicios de limpieza" in d for d in descripciones_no_match
    ), "El filtro q=tecnologia no debería retornar la línea de limpieza"


@pytest.mark.asyncio
async def test_plan_anual_requiere_auth(client: AsyncClient) -> None:
    """GET /futuro/plan-anual sin token → 401."""
    r = await client.get("/api/v1/futuro/plan-anual")
    assert r.status_code == 401
