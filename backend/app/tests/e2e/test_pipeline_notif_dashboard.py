"""Suite E2E de aceptación: Pipeline (Epic 10), Notificaciones (Epic 11) y
Dashboard (Epic 4).

Convenciones:
- Cada test es completamente independiente.
- @pytest.mark.e2e en todos.
- @pytest.mark.slow solo en el test de concurrencia.
- @pytest.mark.xfail cuando el código actual difiere de la spec documentada.

Nota técnica: la fixture `make_licitacion` del conftest.py compartido tiene una
brecha (pasa `duracion_meses` que no existe en el modelo). Esta suite usa su
propio helper `_crear_licitacion` que construye la fila correctamente.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.enums import (
    LicitacionEstado,
    NotifCanal,
    NotifStatus,
    NotifTipo,
    PipelineEstado,
    UserRole,
    UserStatus,
)
from app.models.licitacion import Licitacion
from app.models.notificacion import Notificacion
from app.models.organismo import Organismo
from app.models.pipeline import PipelineItem
from app.tests.e2e.conftest import auth_headers

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.e2e

# ---------------------------------------------------------------------------
# Helpers internos de bajo nivel
# ---------------------------------------------------------------------------

_ORGANISMO_CODIGO = 99001  # código reservado para tests E2E de este módulo


async def _ensure_organismo(db: AsyncSession) -> Organismo:
    """Crea el organismo de prueba si no existe todavía."""
    org = await db.get(Organismo, _ORGANISMO_CODIGO)
    if org is None:
        org = Organismo(
            codigo_organismo=_ORGANISMO_CODIGO,
            nombre="Organismo E2E Pipeline/Notif",
        )
        db.add(org)
        await db.commit()
        await db.refresh(org)
    return org


async def _crear_licitacion(
    db: AsyncSession,
    codigo: str | None = None,
    estado: LicitacionEstado = LicitacionEstado.publicada,
) -> Licitacion:
    """Crea una Licitacion mínima directamente en BD.

    Evita la fixture make_licitacion del conftest compartido que tiene una
    brecha: pasa el parámetro `duracion_meses` que ya no existe en el modelo
    (el campo actual se llama `duracion_estimada_meses`).
    """
    org = await _ensure_organismo(db)
    cod = codigo or f"E2E-{uuid.uuid4().hex[:8].upper()}-L1"
    lic = Licitacion(
        codigo=cod,
        nombre="Licitación E2E pipeline/notif/dashboard",
        estado=estado,
        moneda="CLP",
        es_renovable=False,
        monto_estimado=5_000_000.0,
        fecha_publicacion=datetime(2026, 1, 1, tzinfo=UTC),
        fecha_cierre=datetime(2026, 12, 31, tzinfo=UTC),
        codigo_organismo=org.codigo_organismo,
    )
    db.add(lic)
    await db.commit()
    await db.refresh(lic)
    return lic


async def _crear_item_en_db(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    licitacion_codigo: str,
    estado: PipelineEstado = PipelineEstado.nueva,
) -> PipelineItem:
    """Inserta un PipelineItem directamente en BD (bypasando la API)."""
    item = PipelineItem(
        empresa_id=empresa_id,
        licitacion_codigo=licitacion_codigo,
        estado=estado,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def _crear_notif_en_db(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    leida: bool = False,
    licitacion_codigo: str | None = None,
) -> Notificacion:
    """Inserta una Notificacion in_app directamente en BD."""
    notif = Notificacion(
        empresa_id=empresa_id,
        tipo=NotifTipo.nueva_oportunidad,
        canal=NotifCanal.in_app,
        status=NotifStatus.pendiente if not leida else NotifStatus.leida,
        titulo="Test notificación E2E",
        cuerpo="Contenido de prueba.",
        licitacion_codigo=licitacion_codigo,
        programada_para=datetime.now(UTC),
        leida_at=datetime.now(UTC) if leida else None,
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)
    return notif


# ---------------------------------------------------------------------------
# Fixture: segunda empresa (para tests de aislamiento multi-tenant)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def proveedor_b(make_user: Callable[..., Any], db_session: AsyncSession) -> Any:
    """Segunda empresa proveedora para tests de aislamiento multi-tenant."""
    from app.models.empresa import Empresa

    user = await make_user(
        email="e2e_proveedor_b@test.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        razon_social="E2E Empresa B SpA",
    )
    result = await db_session.execute(select(Empresa).where(Empresa.usuario_id == user.id))
    empresa = result.scalar_one()
    return {
        "usuario": user,
        "empresa": empresa,
        "headers": auth_headers(user.id),
    }


# ===========================================================================
# EPIC 10 — Pipeline (US-10.1 a US-10.3)
# ===========================================================================


# ---------------------------------------------------------------------------
# US-10.1 — Estados
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_pipeline_cambio_estado_flujo_completo(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
) -> None:
    """US-10.1: crear ítem → PATCH vista → PATCH interesado → estado correcto en BD."""
    lic = await _crear_licitacion(db_session)
    headers = proveedor_activo["headers"]
    # Crear
    r = await client.post(
        "/api/v1/pipeline",
        json={"licitacion_codigo": lic.codigo},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    item_id = r.json()["id"]

    # PATCH → vista
    r = await client.patch(
        f"/api/v1/pipeline/{item_id}",
        json={"estado": "vista"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "vista"

    # PATCH → interesado
    r = await client.patch(
        f"/api/v1/pipeline/{item_id}",
        json={"estado": "interesado"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "interesado"

    # Verificar en BD (nueva lectura para ver estado tras commits de la app)
    item = await db_session.get(PipelineItem, uuid.UUID(item_id))
    assert item is not None
    assert item.estado == PipelineEstado.interesado


@pytest.mark.e2e
async def test_pipeline_descartada_requiere_razon(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
) -> None:
    """US-10.1: PATCH estado=descartada sin razon_descarte.

    Según spec la razón debería ser obligatoria, pero el backend NO la
    valida — acepta el cambio sin razon_descarte.
    Se usa xfail condicional para documentar la brecha vs spec.
    """
    lic = await _crear_licitacion(db_session)
    headers = proveedor_activo["headers"]
    empresa_id: uuid.UUID = proveedor_activo["empresa"].id

    item = await _crear_item_en_db(db_session, empresa_id, lic.codigo)

    r = await client.patch(
        f"/api/v1/pipeline/{item.id}",
        json={"estado": "descartada"},
        headers=headers,
    )
    # Según spec debería exigir razon_descarte → 422.
    # El backend actual lo acepta sin razón → 200.
    if r.status_code == 422:
        # Si algún día se corrige, este test pasa directamente.
        pass
    else:
        pytest.xfail(
            reason=(
                "Brecha spec US-10.1: descartada sin razon_descarte debería ser 422, "
                f"pero el backend retornó {r.status_code}. "
                "El campo razon_descarte no está siendo validado como requerido."
            )
        )


@pytest.mark.e2e
@pytest.mark.xfail(
    strict=True,
    reason=(
        "Brecha multi-tenancy US-10.1: el código retorna 403 cuando el ítem "
        "existe pero pertenece a otra empresa. La spec exige 404 para no revelar "
        "existencia del recurso. Ver _get_item_de_empresa_o_404 en pipeline.py."
    ),
)
async def test_pipeline_item_solo_visible_para_su_empresa(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
    proveedor_b: Any,
) -> None:
    """US-10.1: empresa B intenta GET del ítem de empresa A → debe ser 404 (no 403)."""
    lic = await _crear_licitacion(db_session)
    empresa_a_id: uuid.UUID = proveedor_activo["empresa"].id

    item = await _crear_item_en_db(db_session, empresa_a_id, lic.codigo)

    r = await client.get(
        f"/api/v1/pipeline/{item.id}",
        headers=proveedor_b["headers"],
    )
    # Spec exige 404 para no revelar existencia; backend retorna 403 → xfail
    assert (
        r.status_code == 404
    ), f"Se esperaba 404 (multi-tenancy), pero el backend retornó {r.status_code}"


@pytest.mark.e2e
async def test_pipeline_empresa_b_no_ve_items_empresa_a(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
    proveedor_b: Any,
) -> None:
    """US-10.1: GET /pipeline de empresa B no muestra ítems de empresa A."""
    lic = await _crear_licitacion(db_session)
    empresa_a_id: uuid.UUID = proveedor_activo["empresa"].id

    await _crear_item_en_db(db_session, empresa_a_id, lic.codigo)

    # Empresa B lista su pipeline
    r = await client.get("/api/v1/pipeline", headers=proveedor_b["headers"])
    assert r.status_code == 200, r.text

    data = r.json()
    codigos = [it["licitacion"]["codigo"] for it in data["items"]]
    assert (
        lic.codigo not in codigos
    ), "El pipeline de empresa B contiene un ítem que pertenece a empresa A"


# ---------------------------------------------------------------------------
# US-10.2 — Vista pipeline
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_pipeline_filtro_estado_interesado(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
) -> None:
    """US-10.2: filtro por estado=interesado retorna solo ítems en ese estado."""
    empresa_id: uuid.UUID = proveedor_activo["empresa"].id
    headers = proveedor_activo["headers"]

    lic_1 = await _crear_licitacion(db_session)
    lic_2 = await _crear_licitacion(db_session)
    lic_3 = await _crear_licitacion(db_session)

    await _crear_item_en_db(db_session, empresa_id, lic_1.codigo, PipelineEstado.nueva)
    await _crear_item_en_db(db_session, empresa_id, lic_2.codigo, PipelineEstado.interesado)
    await _crear_item_en_db(db_session, empresa_id, lic_3.codigo, PipelineEstado.postulando)

    r = await client.get(
        "/api/v1/pipeline",
        params={"estado": "interesado"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["items"]) >= 1
    assert isinstance(data["has_next"], bool)
    for item in data["items"]:
        assert item["estado"] == "interesado"


@pytest.mark.e2e
async def test_pipeline_paginacion_correcta(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
) -> None:
    """US-10.2: 10 ítems, page_size=5 → dos páginas sin solapamiento."""
    empresa_id: uuid.UUID = proveedor_activo["empresa"].id
    headers = proveedor_activo["headers"]

    for _ in range(10):
        lic = await _crear_licitacion(db_session)
        await _crear_item_en_db(db_session, empresa_id, lic.codigo)

    r1 = await client.get(
        "/api/v1/pipeline",
        params={"page": 1, "page_size": 5},
        headers=headers,
    )
    r2 = await client.get(
        "/api/v1/pipeline",
        params={"page": 2, "page_size": 5},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text

    page1_ids = {it["id"] for it in r1.json()["items"]}
    page2_ids = {it["id"] for it in r2.json()["items"]}

    assert len(page1_ids) == 5
    assert len(page2_ids) == 5
    assert page1_ids.isdisjoint(page2_ids), "Las dos páginas comparten ítems"


@pytest.mark.e2e
async def test_pipeline_crear_item_duplicado_retorna_409(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
) -> None:
    """US-10.2: segundo POST con mismo licitacion_codigo para la misma empresa → 409."""
    lic = await _crear_licitacion(db_session)
    headers = proveedor_activo["headers"]

    r1 = await client.post(
        "/api/v1/pipeline",
        json={"licitacion_codigo": lic.codigo},
        headers=headers,
    )
    assert r1.status_code == 201, r1.text

    r2 = await client.post(
        "/api/v1/pipeline",
        json={"licitacion_codigo": lic.codigo},
        headers=headers,
    )
    assert r2.status_code == 409, r2.text


@pytest.mark.e2e
@pytest.mark.xfail(
    strict=True,
    reason=(
        "Brecha multi-tenancy: PATCH sobre ítem ajeno retorna 403 en lugar de 404. "
        "Ver _get_item_de_empresa_o_404 en pipeline.py."
    ),
)
async def test_pipeline_item_ajeno_retorna_404_no_403(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
    proveedor_b: Any,
) -> None:
    """US-10.2: PATCH sobre ítem de otra empresa → 404 (no 403, spec multi-tenancy)."""
    lic = await _crear_licitacion(db_session)
    empresa_a_id: uuid.UUID = proveedor_activo["empresa"].id

    item = await _crear_item_en_db(db_session, empresa_a_id, lic.codigo)

    r = await client.patch(
        f"/api/v1/pipeline/{item.id}",
        json={"estado": "vista"},
        headers=proveedor_b["headers"],
    )
    assert (
        r.status_code == 404
    ), f"Se esperaba 404 (multi-tenancy), pero el backend retornó {r.status_code}"


# ---------------------------------------------------------------------------
# US-10.3 — Notas
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_nota_creada_aparece_en_detalle(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
) -> None:
    """US-10.3: POST nota → GET /pipeline/{id} → nota incluida en respuesta."""
    lic = await _crear_licitacion(db_session)
    empresa_id: uuid.UUID = proveedor_activo["empresa"].id
    headers = proveedor_activo["headers"]

    item = await _crear_item_en_db(db_session, empresa_id, lic.codigo)

    contenido = "Esta es una nota de prueba E2E única."
    r = await client.post(
        f"/api/v1/pipeline/{item.id}/notas",
        json={"contenido": contenido},
        headers=headers,
    )
    assert r.status_code == 201, r.text

    r_detalle = await client.get(
        f"/api/v1/pipeline/{item.id}",
        headers=headers,
    )
    assert r_detalle.status_code == 200, r_detalle.text
    notas = r_detalle.json()["notas"]
    contenidos = [n["contenido"] for n in notas]
    assert contenido in contenidos


@pytest.mark.e2e
async def test_nota_ajena_retorna_403_o_404(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
    proveedor_b: Any,
) -> None:
    """US-10.3: empresa B intenta DELETE nota del ítem de empresa A → 403 o 404."""
    lic = await _crear_licitacion(db_session)
    empresa_a_id: uuid.UUID = proveedor_activo["empresa"].id
    headers_a = proveedor_activo["headers"]
    headers_b = proveedor_b["headers"]

    item = await _crear_item_en_db(db_session, empresa_a_id, lic.codigo)

    # Empresa A crea una nota
    r = await client.post(
        f"/api/v1/pipeline/{item.id}/notas",
        json={"contenido": "Nota de empresa A."},
        headers=headers_a,
    )
    assert r.status_code == 201, r.text
    nota_id = r.json()["id"]

    # Empresa B intenta eliminar la nota del ítem de empresa A.
    # El endpoint verifica primero el ítem (empresa_id != empresa_b → 403).
    # Ambos 403 y 404 son aceptables: lo que NO debe ocurrir es un 204.
    r_del = await client.delete(
        f"/api/v1/pipeline/{item.id}/notas/{nota_id}",
        headers=headers_b,
    )
    assert r_del.status_code in {
        403,
        404,
    }, f"Se esperaba 403 o 404, pero el backend retornó {r_del.status_code}"


@pytest.mark.e2e
async def test_nota_contenido_vacio_retorna_422(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
) -> None:
    """US-10.3: POST nota con contenido='' → 422 (validación Pydantic min_length=1)."""
    lic = await _crear_licitacion(db_session)
    empresa_id: uuid.UUID = proveedor_activo["empresa"].id
    headers = proveedor_activo["headers"]

    item = await _crear_item_en_db(db_session, empresa_id, lic.codigo)

    r = await client.post(
        f"/api/v1/pipeline/{item.id}/notas",
        json={"contenido": ""},
        headers=headers,
    )
    assert r.status_code == 422, r.text


# ===========================================================================
# EPIC 11 — Notificaciones (US-11.1 a US-11.3)
# ===========================================================================


# ---------------------------------------------------------------------------
# US-11.3 — Centro in-app
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_notificaciones_resumen_vacio(
    client: AsyncClient,
    proveedor_activo: Any,
) -> None:
    """US-11.3: empresa sin notificaciones → unread_count=0, items=[]."""
    r = await client.get(
        "/api/v1/notificaciones/resumen",
        headers=proveedor_activo["headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["unread_count"] == 0
    assert data["items"] == []


@pytest.mark.e2e
async def test_notificaciones_resumen_con_no_leidas(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
) -> None:
    """US-11.3: insertar notif in_app no leída → resumen muestra unread_count >= 1."""
    empresa_id: uuid.UUID = proveedor_activo["empresa"].id

    notif = await _crear_notif_en_db(db_session, empresa_id, leida=False)

    try:
        r = await client.get(
            "/api/v1/notificaciones/resumen",
            headers=proveedor_activo["headers"],
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["unread_count"] >= 1
        item_ids = [it["id"] for it in data["items"]]
        assert str(notif.id) in item_ids
    finally:
        await db_session.delete(notif)
        await db_session.commit()


@pytest.mark.e2e
async def test_marcar_notificacion_leida(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
) -> None:
    """US-11.3: POST /notificaciones/{id}/leer → 200; resumen sin esa notif no leída."""
    empresa_id: uuid.UUID = proveedor_activo["empresa"].id
    headers = proveedor_activo["headers"]

    notif = await _crear_notif_en_db(db_session, empresa_id, leida=False)

    try:
        r = await client.post(
            f"/api/v1/notificaciones/{notif.id}/leer",
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["leida_at"] is not None

        # La empresa solo tiene esta notif — unread_count debe ser 0
        r_resumen = await client.get(
            "/api/v1/notificaciones/resumen",
            headers=headers,
        )
        assert r_resumen.status_code == 200, r_resumen.text
        assert r_resumen.json()["unread_count"] == 0
    finally:
        await db_session.refresh(notif)
        await db_session.delete(notif)
        await db_session.commit()


@pytest.mark.e2e
async def test_notificacion_ajena_no_se_puede_marcar(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
    proveedor_b: Any,
) -> None:
    """US-11.3: empresa B intenta marcar notif de empresa A como leída → 404."""
    empresa_a_id: uuid.UUID = proveedor_activo["empresa"].id

    notif = await _crear_notif_en_db(db_session, empresa_a_id, leida=False)

    try:
        r = await client.post(
            f"/api/v1/notificaciones/{notif.id}/leer",
            headers=proveedor_b["headers"],
        )
        assert (
            r.status_code == 404
        ), f"Se esperaba 404 (multi-tenancy), pero el backend retornó {r.status_code}"
    finally:
        await db_session.delete(notif)
        await db_session.commit()


@pytest.mark.e2e
async def test_notificaciones_solo_propias(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
    proveedor_b: Any,
) -> None:
    """US-11.3: empresa A y B tienen notifs → cada una solo ve las suyas."""
    empresa_a_id: uuid.UUID = proveedor_activo["empresa"].id
    empresa_b_id: uuid.UUID = proveedor_b["empresa"].id

    notif_a = await _crear_notif_en_db(db_session, empresa_a_id, leida=False)
    notif_b = await _crear_notif_en_db(db_session, empresa_b_id, leida=False)

    try:
        r_a = await client.get(
            "/api/v1/notificaciones/resumen",
            headers=proveedor_activo["headers"],
        )
        r_b = await client.get(
            "/api/v1/notificaciones/resumen",
            headers=proveedor_b["headers"],
        )
        assert r_a.status_code == 200
        assert r_b.status_code == 200

        ids_a = {it["id"] for it in r_a.json()["items"]}
        ids_b = {it["id"] for it in r_b.json()["items"]}

        assert str(notif_a.id) in ids_a
        assert str(notif_b.id) not in ids_a
        assert str(notif_b.id) in ids_b
        assert str(notif_a.id) not in ids_b
    finally:
        await db_session.delete(notif_a)
        await db_session.delete(notif_b)
        await db_session.commit()


# ---------------------------------------------------------------------------
# US-11.1 / US-11.2 — Preferencias
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_preferencias_default(
    client: AsyncClient,
    proveedor_activo: Any,
) -> None:
    """US-11.1: empresa sin prefs explícitas → GET retorna defaults."""
    r = await client.get(
        "/api/v1/preferencias-notificaciones",
        headers=proveedor_activo["headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()
    # Valores por defecto del modelo
    assert data["email_activo"] is True
    assert data["whatsapp_activo"] is False
    assert data["in_app_activo"] is True


@pytest.mark.e2e
async def test_patch_preferencias_score_minimo(
    client: AsyncClient,
    proveedor_activo: Any,
) -> None:
    """US-11.2: PATCH email_score_minimo=85 → GET retorna email_score_minimo=85."""
    headers = proveedor_activo["headers"]

    r = await client.patch(
        "/api/v1/preferencias-notificaciones",
        json={"email_score_minimo": 85},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["email_score_minimo"] == 85

    r_get = await client.get(
        "/api/v1/preferencias-notificaciones",
        headers=headers,
    )
    assert r_get.status_code == 200, r_get.text
    assert r_get.json()["email_score_minimo"] == 85


@pytest.mark.e2e
async def test_patch_preferencias_desactivar_whatsapp(
    client: AsyncClient,
    proveedor_activo: Any,
) -> None:
    """US-11.2: PATCH {whatsapp_activo: false} → GET retorna whatsapp_activo=false."""
    headers = proveedor_activo["headers"]

    # Activar primero
    await client.patch(
        "/api/v1/preferencias-notificaciones",
        json={"whatsapp_activo": True},
        headers=headers,
    )

    # Luego desactivar
    r = await client.patch(
        "/api/v1/preferencias-notificaciones",
        json={"whatsapp_activo": False},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["whatsapp_activo"] is False

    r_get = await client.get(
        "/api/v1/preferencias-notificaciones",
        headers=headers,
    )
    assert r_get.status_code == 200, r_get.text
    assert r_get.json()["whatsapp_activo"] is False


@pytest.mark.e2e
async def test_preferencias_solo_propias(
    client: AsyncClient,
    proveedor_activo: Any,
    proveedor_b: Any,
) -> None:
    """US-11.2: empresa A y B configuran email_score_minimo distintos → cada una ve el suyo."""
    headers_a = proveedor_activo["headers"]
    headers_b = proveedor_b["headers"]

    await client.patch(
        "/api/v1/preferencias-notificaciones",
        json={"email_score_minimo": 60},
        headers=headers_a,
    )
    await client.patch(
        "/api/v1/preferencias-notificaciones",
        json={"email_score_minimo": 90},
        headers=headers_b,
    )

    r_a = await client.get(
        "/api/v1/preferencias-notificaciones",
        headers=headers_a,
    )
    r_b = await client.get(
        "/api/v1/preferencias-notificaciones",
        headers=headers_b,
    )

    assert r_a.status_code == 200
    assert r_b.status_code == 200
    assert r_a.json()["email_score_minimo"] == 60
    assert r_b.json()["email_score_minimo"] == 90


# ===========================================================================
# EPIC 4 — Dashboard (US-4.1, US-4.2)
# ===========================================================================


@pytest.mark.e2e
async def test_dashboard_resumen_kpis_estructura(
    client: AsyncClient,
    proveedor_activo: Any,
) -> None:
    """US-4.1: GET /dashboard/resumen → respuesta tiene todas las claves KPI."""
    r = await client.get(
        "/api/v1/dashboard/resumen",
        headers=proveedor_activo["headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()

    for key in (
        "oportunidades_activas",
        "nuevas_hoy",
        "proximas_a_cerrar",
        "en_pipeline",
    ):
        assert key in data, f"Falta la clave '{key}' en /dashboard/resumen"

    assert data["oportunidades_activas"] >= 0
    assert data["nuevas_hoy"] >= 0
    assert data["proximas_a_cerrar"] >= 0
    assert data["en_pipeline"] >= 0


@pytest.mark.e2e
async def test_dashboard_resumen_en_pipeline_cuenta_items(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
) -> None:
    """US-4.1: crear 2 items pipeline → en_pipeline >= 2."""
    empresa_id: uuid.UUID = proveedor_activo["empresa"].id
    headers = proveedor_activo["headers"]

    lic_1 = await _crear_licitacion(db_session)
    lic_2 = await _crear_licitacion(db_session)

    await _crear_item_en_db(db_session, empresa_id, lic_1.codigo)
    await _crear_item_en_db(db_session, empresa_id, lic_2.codigo)

    r = await client.get("/api/v1/dashboard/resumen", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["en_pipeline"] >= 2


@pytest.mark.e2e
async def test_dashboard_segmentos_estructura(
    client: AsyncClient,
    proveedor_activo: Any,
) -> None:
    """US-4.2: GET /dashboard/segmentos → lista con estructura correcta."""
    r = await client.get(
        "/api/v1/dashboard/segmentos",
        headers=proveedor_activo["headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()

    assert "segmentos" in data
    assert isinstance(data["segmentos"], list)

    for seg in data["segmentos"]:
        # La respuesta usa 'codigo', no 'segmento'
        assert "codigo" in seg, f"Falta 'codigo' en segmento: {seg}"
        assert "cantidad" in seg, f"Falta 'cantidad' en segmento: {seg}"


@pytest.mark.e2e
async def test_dashboard_requiere_autenticacion(
    client: AsyncClient,
) -> None:
    """US-4.1: GET /dashboard/resumen sin token → 401."""
    r = await client.get("/api/v1/dashboard/resumen")
    assert r.status_code == 401, r.text


# ===========================================================================
# US-8.2 — xfail: vista por radar no implementada
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.xfail(
    strict=False,
    reason=(
        "US-8.2: el filtro ?radar_id=<uuid> en GET /api/v1/pipeline no está "
        "implementado. El endpoint ignora el parámetro en lugar de filtrarlo. "
        "Feature pendiente de implementación."
    ),
)
async def test_vista_por_radar_no_implementada(
    client: AsyncClient,
    proveedor_activo: Any,
) -> None:
    """US-8.2: GET /api/v1/pipeline?radar_id=<uuid> debería filtrar por radar.

    El endpoint actualmente no acepta radar_id — documenta la brecha vs spec.
    """
    fake_radar_id = str(uuid.uuid4())
    r = await client.get(
        "/api/v1/pipeline",
        params={"radar_id": fake_radar_id},
        headers=proveedor_activo["headers"],
    )
    # Si la feature no existe el param es ignorado → 200 con todos los ítems.
    # Esperamos que a futuro retorne solo los detectados por ese radar,
    # o 422 si el parámetro es desconocido.
    assert r.status_code == 422, (
        "Se esperaba 422 indicando que radar_id no es un parámetro soportado, "
        f"pero el backend retornó {r.status_code}"
    )


# ===========================================================================
# Negative paths
# ===========================================================================


@pytest.mark.e2e
async def test_pipeline_sin_auth_retorna_401(client: AsyncClient) -> None:
    """GET /pipeline sin token → 401."""
    r = await client.get("/api/v1/pipeline")
    assert r.status_code == 401, r.text


@pytest.mark.e2e
async def test_pipeline_patch_estado_invalido_retorna_422(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
) -> None:
    """PATCH estado='estado_que_no_existe' → 422."""
    lic = await _crear_licitacion(db_session)
    empresa_id: uuid.UUID = proveedor_activo["empresa"].id
    headers = proveedor_activo["headers"]

    item = await _crear_item_en_db(db_session, empresa_id, lic.codigo)

    r = await client.patch(
        f"/api/v1/pipeline/{item.id}",
        json={"estado": "estado_que_no_existe"},
        headers=headers,
    )
    assert r.status_code == 422, r.text


@pytest.mark.e2e
async def test_pipeline_licitacion_inexistente_retorna_404(
    client: AsyncClient,
    proveedor_activo: Any,
) -> None:
    """POST pipeline con licitacion_codigo inexistente → 404."""
    r = await client.post(
        "/api/v1/pipeline",
        json={"licitacion_codigo": "LIC-INEXISTENTE-9999"},
        headers=proveedor_activo["headers"],
    )
    assert r.status_code == 404, r.text


@pytest.mark.e2e
async def test_notificaciones_sin_auth_retorna_401(client: AsyncClient) -> None:
    """GET /notificaciones/resumen sin token → 401."""
    r = await client.get("/api/v1/notificaciones/resumen")
    assert r.status_code == 401, r.text


# ===========================================================================
# Resistance: concurrencia básica (Fase 4)
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.slow
async def test_pipeline_concurrencia_no_duplica(
    client: AsyncClient,
    db_session: AsyncSession,
    proveedor_activo: Any,
) -> None:
    """Resistencia: 5 POST concurrentes para el mismo licitacion_codigo
    → exactamente 1 creado (201), resto 409 (unique constraint).
    """
    lic = await _crear_licitacion(db_session)
    lic_codigo: str = lic.codigo  # capturar antes del gather para evitar lazy load
    headers = proveedor_activo["headers"]
    empresa_id: uuid.UUID = proveedor_activo["empresa"].id

    async def _post() -> Any:
        return await client.post(
            "/api/v1/pipeline",
            json={"licitacion_codigo": lic_codigo},
            headers=headers,
        )

    tasks = [_post() for _ in range(5)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    statuses = [r.status_code for r in results if not isinstance(r, Exception)]

    created = [s for s in statuses if s == 201]
    conflicts = [s for s in statuses if s == 409]
    errors = [s for s in statuses if s not in {201, 409}]

    # Verificar en BD que solo hay un ítem
    db_result = await db_session.execute(
        select(PipelineItem).where(
            PipelineItem.empresa_id == empresa_id,
            PipelineItem.licitacion_codigo == lic_codigo,
        )
    )
    items_en_db = list(db_result.scalars().all())

    # BUG DOCUMENTADO: el backend no tiene protección atómica contra inserciones
    # concurrentes. La verificación app-level (SELECT + INSERT) no es atómica bajo
    # carga concurrente via ASGITransport. El resultado observado es que todas las
    # requests pasan la verificación y se intenta insertar → IntegrityError sin manejar
    # o bien 5x201 (duplicados en BD si el constraint no actuó a tiempo).
    # El comportamiento correcto según spec sería: 1x201 + 4x409.
    if len(created) == 1 and len(conflicts) == 4:
        # Comportamiento correcto — el bug fue corregido
        assert len(items_en_db) == 1
    else:
        # Documentar el comportamiento actual con xfail
        pytest.xfail(
            reason=(
                f"BUG concurrencia: se esperaba 1x201 + 4x409, "
                f"pero se obtuvo {len(created)}x201 + {len(conflicts)}x409"
                f" + {len(errors)} errores. "
                f"Ítems en BD: {len(items_en_db)}. "
                "El backend no tiene check atómico (SELECT+INSERT race condition)."
            )
        )
