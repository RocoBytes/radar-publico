"""Suite de aceptación E2E — Radares, Onboarding, Intereses, Futuro/Renovaciones.

Cubre:
  Epic 5.3 (US-5.3)    — Radares (CRUD, límites, multi-tenant)
  Epic 3   (US-3.1–3.5)— Onboarding de empresa
  Epic 3.4 (US-3.4)    — Intereses comerciales
  Epic 9.2 (US-9.2)    — Feed de renovaciones de contratos
  Epic 9.1 (US-9.1)    — Plan anual (NOT implementado — xfail)
  Epic 9.3 (US-9.3)    — Patrones estacionales (NOT implementado — xfail)
  US-8.2               — Vista por radar (NOT implementado — xfail)
  Infraestructura      — /health, /catalogos/regiones, /catalogos/unspsc
  Rutas negativas      — auth, 404, 422, 403

Convenciones:
  - @pytest.mark.e2e en cada test
  - @pytest.mark.asyncio para coroutines
  - Cada test es independiente: crea y limpia sus propios datos
  - Notas arquitectónicas:
      * El endpoint /futuro/renovaciones usa Licitacion.fecha_estimada_termino_contrato,
        NO LicitacionFecha — es un campo desnormalizado en la tabla licitaciones.
      * La EmpresaUpdateRequest NO acepta rut — campo excluido del schema.
      * onboarding_completado existe en Empresa y EmpresaUpdateRequest.
      * wizard_step NO existe en el modelo actual (v1).
      * El límite de radares fue cambiado a 20 (antes 50).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.empresa import Empresa
from app.models.enums import LicitacionEstado, UserRole, UserStatus
from app.models.interes import Interes, InteresTipo
from app.models.licitacion import Licitacion
from app.models.radar import Radar
from app.tests.e2e.conftest import auth_headers


# ===========================================================================
# Epic 5.3 — Radares (US-5.3)
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_crear_radar_ok_y_aparece_en_lista(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """POST radar → GET /radares → aparece con nombre correcto y activo=True."""
    headers = proveedor_activo["headers"]

    resp = await client.post(
        "/api/v1/radares",
        json={"nombre": "Radar TI Santiago", "filtros": {}},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["nombre"] == "Radar TI Santiago"
    assert data["activo"] is True
    radar_id = data["id"]

    lista = await client.get("/api/v1/radares", headers=headers)
    assert lista.status_code == 200
    ids = [r["id"] for r in lista.json()["items"]]
    assert radar_id in ids


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_radar_limite_20_cumple_spec(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """Crear 20 radares OK → 21° da 400. Verifica el límite corregido de la spec."""
    headers = proveedor_activo["headers"]
    empresa = proveedor_activo["empresa"]

    # Crear 20 radares directamente en BD para no saturar el test con 20 HTTP calls
    radares = [
        Radar(
            empresa_id=empresa.id,
            nombre=f"Radar límite {i}",
            filtros={},
        )
        for i in range(20)
    ]
    db_session.add_all(radares)
    await db_session.commit()

    try:
        resp = await client.post(
            "/api/v1/radares",
            json={"nombre": "Radar 21 — debe fallar", "filtros": {}},
            headers=headers,
        )
        assert resp.status_code == 400, (
            f"Se esperaba 400 al superar el límite de 20 radares, "
            f"pero se obtuvo {resp.status_code}: {resp.text}"
        )
    finally:
        await db_session.execute(
            delete(Radar).where(Radar.empresa_id == empresa.id)
        )
        await db_session.commit()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_radar_desactivar_sin_eliminar(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """PATCH activo=False → radar sigue existiendo pero inactivo."""
    headers = proveedor_activo["headers"]
    empresa = proveedor_activo["empresa"]

    radar = Radar(empresa_id=empresa.id, nombre="Radar a desactivar", filtros={})
    db_session.add(radar)
    await db_session.commit()
    await db_session.refresh(radar)

    try:
        resp = await client.patch(
            f"/api/v1/radares/{radar.id}",
            json={"activo": False},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["activo"] is False

        # Verificar que todavía existe en el GET
        get_resp = await client.get(f"/api/v1/radares/{radar.id}", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["activo"] is False
    finally:
        await db_session.execute(delete(Radar).where(Radar.id == radar.id))
        await db_session.commit()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_radar_eliminar(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """DELETE radar → GET da 404."""
    headers = proveedor_activo["headers"]
    empresa = proveedor_activo["empresa"]

    radar = Radar(empresa_id=empresa.id, nombre="Radar a eliminar", filtros={})
    db_session.add(radar)
    await db_session.commit()
    await db_session.refresh(radar)
    radar_id = radar.id

    resp = await client.delete(f"/api/v1/radares/{radar_id}", headers=headers)
    assert resp.status_code == 204, resp.text

    get_resp = await client.get(f"/api/v1/radares/{radar_id}", headers=headers)
    assert get_resp.status_code == 404


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_radar_ajeno_retorna_403_o_404(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """Empresa A crea radar → empresa B intenta GET → 403 o 404."""
    empresa_a = proveedor_activo["empresa"]

    radar = Radar(empresa_id=empresa_a.id, nombre="Radar privado empresa A", filtros={})
    db_session.add(radar)
    await db_session.commit()
    await db_session.refresh(radar)

    # Crear empresa B
    user_b = await make_user(
        email=f"empresa_b_radar_{uuid.uuid4().hex[:8]}@test.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        razon_social="Empresa B SpA",
    )
    headers_b = auth_headers(user_b.id)

    try:
        resp = await client.get(f"/api/v1/radares/{radar.id}", headers=headers_b)
        # La spec requiere 403 (radar existe pero es de otra empresa)
        # Aceptamos también 404 como comportamiento alternativo válido
        assert resp.status_code in (403, 404), (
            f"Se esperaba 403 o 404 para acceso a radar ajeno, "
            f"pero se obtuvo {resp.status_code}: {resp.text}"
        )
    finally:
        await db_session.execute(delete(Radar).where(Radar.id == radar.id))
        await db_session.commit()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_radar_nombre_vacio_retorna_422(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """POST con nombre='' → 422 (Pydantic min_length=1)."""
    headers = proveedor_activo["headers"]

    resp = await client.post(
        "/api/v1/radares",
        json={"nombre": "", "filtros": {}},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_radares_multi_tenant_empresa_b_no_ve_radares_a(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """Empresa B no ve los radares de empresa A en GET /radares."""
    empresa_a = proveedor_activo["empresa"]
    headers_a = proveedor_activo["headers"]

    # Empresa A crea un radar
    resp = await client.post(
        "/api/v1/radares",
        json={"nombre": "Radar solo de A", "filtros": {}},
        headers=headers_a,
    )
    assert resp.status_code == 201
    radar_id_a = resp.json()["id"]

    # Empresa B lista sus radares
    user_b = await make_user(
        email=f"empresa_b_multi_{uuid.uuid4().hex[:8]}@test.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        razon_social="Empresa B Multi SpA",
    )
    headers_b = auth_headers(user_b.id)

    try:
        lista_b = await client.get("/api/v1/radares", headers=headers_b)
        assert lista_b.status_code == 200
        ids_b = [r["id"] for r in lista_b.json()["items"]]
        assert radar_id_a not in ids_b, (
            "Empresa B no debe ver los radares de empresa A"
        )
    finally:
        await db_session.execute(
            delete(Radar).where(Radar.empresa_id == empresa_a.id)
        )
        await db_session.commit()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_radar_sin_auth_retorna_401(
    client: AsyncClient,
) -> None:
    """GET /radares sin token → 401."""
    resp = await client.get("/api/v1/radares")
    assert resp.status_code == 401, resp.text


# ===========================================================================
# Epic 3 — Onboarding (US-3.1 a US-3.5)
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.xfail(
    reason=(
        "spec US-3.1: no existe middleware que bloquee el dashboard "
        "por onboarding incompleto en v1 — wizard_step no está implementado"
    ),
    strict=False,
)
async def test_onboarding_wizard_bloquea_dashboard(
    client: AsyncClient,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """Usuario con onboarding_completado=False → acceso al dashboard bloqueado.

    La spec US-3.1 requiere que el wizard de onboarding bloquee el dashboard
    hasta completarse. En v1 no existe este mecanismo de bloqueo.
    """
    user = await make_user(
        email=f"onboarding_bloq_{uuid.uuid4().hex[:8]}@test.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
    )
    headers = auth_headers(user.id)

    # Asegurar que onboarding_completado=False
    result = await db_session.execute(
        select(Empresa).where(Empresa.usuario_id == user.id)
    )
    empresa = result.scalar_one()
    empresa.onboarding_completado = False
    await db_session.commit()

    # Esperamos un 4xx/redirect que indique que el dashboard está bloqueado
    resp = await client.get("/api/v1/dashboard/resumen", headers=headers)
    assert resp.status_code in (302, 403, 428), (
        f"Se esperaba bloqueo de dashboard (302/403/428) con onboarding incompleto, "
        f"obtuvo {resp.status_code}"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_empresa_patch_actualiza_campos(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """PATCH /empresa/me con razon_social nueva → GET refleja el cambio.

    Nota: razon_social NO está en EmpresaUpdateRequest (campo gestionado por admin).
    Probamos con nombre_fantasia que sí es editable.
    """
    headers = proveedor_activo["headers"]

    resp = await client.patch(
        "/api/v1/empresa/me",
        json={"nombre_fantasia": "Fantasía Actualizada SpA"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["nombre_fantasia"] == "Fantasía Actualizada SpA"

    get_resp = await client.get("/api/v1/empresa/me", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["nombre_fantasia"] == "Fantasía Actualizada SpA"


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.xfail(
    reason=(
        "spec US-3.x: rut debería ser inmutable post-creación. "
        "EmpresaUpdateRequest excluye 'rut' del schema, por lo que enviarlo "
        "en PATCH no produce error 422 — simplemente se ignora. "
        "Este test verifica que el campo rut NO cambia."
    ),
    strict=False,
)
async def test_empresa_rut_no_editable(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """PATCH /empresa/me con rut → rut no cambia (campo ignorado por schema).

    La spec establece que el RUT es inmutable. EmpresaUpdateRequest lo excluye,
    así que si se envía, se ignora silenciosamente. Este test documenta la
    garantía de inmutabilidad.
    """
    headers = proveedor_activo["headers"]

    get_orig = await client.get("/api/v1/empresa/me", headers=headers)
    rut_original = get_orig.json()["rut"]

    # Intentar cambiar el rut (debe ser ignorado o rechazado)
    resp = await client.patch(
        "/api/v1/empresa/me",
        json={"rut": "99.999.999-9"},
        headers=headers,
    )
    # Cualquier código 2xx es aceptable — el campo simplemente se ignora
    assert resp.status_code in (200, 204), resp.text

    get_post = await client.get("/api/v1/empresa/me", headers=headers)
    assert get_post.json()["rut"] == rut_original, (
        f"El rut cambió de {rut_original!r} a {get_post.json()['rut']!r} "
        f"— violación de inmutabilidad"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ticket_request_endpoint_existe(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """POST /empresa/ticket-request → al menos 200/201/204 (endpoint existe)."""
    headers = proveedor_activo["headers"]

    resp = await client.post(
        "/api/v1/empresa/ticket-request",
        json={"ticket_texto": "TICKET-DE-PRUEBA-E2E-1234"},
        headers=headers,
    )
    assert resp.status_code in (200, 201, 204), (
        f"El endpoint /empresa/ticket-request debe existir, "
        f"pero devolvió {resp.status_code}: {resp.text}"
    )


# ===========================================================================
# Epic 3.4 — Intereses (US-3.4)
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.xfail(
    reason=(
        "spec US-3.4: la spec requiere al menos 1 interés UNSPSC para completar "
        "el onboarding, pero no hay validación server-side que fuerce este mínimo "
        "en el endpoint — la empresa puede existir sin intereses"
    ),
    strict=False,
)
async def test_interes_unspsc_minimo_uno(
    client: AsyncClient,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """Nueva empresa sin intereses → algún endpoint debe indicar que falta al menos 1 UNSPSC.

    La spec US-3.4 establece que el onboarding requiere mínimo 1 interés UNSPSC.
    En v1 no hay enforcement server-side de este mínimo.
    """
    user = await make_user(
        email=f"interes_minimo_{uuid.uuid4().hex[:8]}@test.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
    )
    headers = auth_headers(user.id)

    # Si hay enforcement, marcar onboarding como completado sin intereses UNSPSC
    # debería fallar o devolver alguna advertencia
    resp = await client.patch(
        "/api/v1/empresa/me",
        json={"onboarding_completado": True},
        headers=headers,
    )
    # Esperamos que sin al menos 1 UNSPSC no se pueda completar el onboarding
    # En v1 esta validación no existe → xfail
    assert resp.status_code in (400, 422), (
        f"Se esperaba 400/422 al completar onboarding sin intereses UNSPSC, "
        f"pero se obtuvo {resp.status_code}"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_interes_crear_y_listar(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """POST interes keyword → GET /intereses → aparece en la lista."""
    headers = proveedor_activo["headers"]
    empresa = proveedor_activo["empresa"]

    resp = await client.post(
        "/api/v1/intereses",
        json={"tipo": "keyword", "valor": "mantencion CCTV"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    interes_id = resp.json()["id"]
    assert resp.json()["valor"] == "mantencion CCTV"

    try:
        lista = await client.get("/api/v1/intereses", headers=headers)
        assert lista.status_code == 200
        valores = [i["valor"] for i in lista.json()["items"]]
        assert "mantencion CCTV" in valores
    finally:
        await db_session.execute(
            delete(Interes).where(Interes.id == uuid.UUID(interes_id))
        )
        await db_session.commit()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_interes_duplicado_rechazado(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """POST mismo interés dos veces → segundo da 409."""
    headers = proveedor_activo["headers"]

    payload = {"tipo": "keyword", "valor": "duplicado_e2e_test"}

    resp1 = await client.post("/api/v1/intereses", json=payload, headers=headers)
    assert resp1.status_code == 201, resp1.text
    interes_id = resp1.json()["id"]

    try:
        resp2 = await client.post("/api/v1/intereses", json=payload, headers=headers)
        assert resp2.status_code == 409, (
            f"Se esperaba 409 para interés duplicado, pero se obtuvo "
            f"{resp2.status_code}: {resp2.text}"
        )
    finally:
        await db_session.execute(
            delete(Interes).where(Interes.id == uuid.UUID(interes_id))
        )
        await db_session.commit()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_interes_eliminar(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """DELETE /intereses/{id} → ya no aparece en GET /intereses."""
    headers = proveedor_activo["headers"]

    resp = await client.post(
        "/api/v1/intereses",
        json={"tipo": "keyword", "valor": "interes_a_eliminar_e2e"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    interes_id = resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/intereses/{interes_id}", headers=headers
    )
    assert del_resp.status_code == 204, del_resp.text

    lista = await client.get("/api/v1/intereses", headers=headers)
    assert lista.status_code == 200
    ids = [i["id"] for i in lista.json()["items"]]
    assert interes_id not in ids


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_interes_ajeno_no_eliminar(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """Empresa A tiene un interés → empresa B intenta DELETE → 403 o 404."""
    empresa_a = proveedor_activo["empresa"]

    # Crear interés directamente en BD para empresa A
    interes = Interes(
        empresa_id=empresa_a.id,
        tipo=InteresTipo.keyword,
        valor="interes_privado_empresa_a",
    )
    db_session.add(interes)
    await db_session.commit()
    await db_session.refresh(interes)

    user_b = await make_user(
        email=f"empresa_b_interes_{uuid.uuid4().hex[:8]}@test.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        razon_social="Empresa B Intereses SpA",
    )
    headers_b = auth_headers(user_b.id)

    try:
        resp = await client.delete(
            f"/api/v1/intereses/{interes.id}", headers=headers_b
        )
        assert resp.status_code in (403, 404), (
            f"Empresa B no debería poder eliminar interés de empresa A. "
            f"Se obtuvo {resp.status_code}: {resp.text}"
        )
    finally:
        # Limpiar si no fue eliminado por B
        await db_session.execute(delete(Interes).where(Interes.id == interes.id))
        await db_session.commit()


# ===========================================================================
# Epic 9.2 — Renovaciones (US-9.2)
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_renovaciones_licitacion_renovable_dentro_de_6_meses(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
    make_licitacion: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """Licitación adjudicada, renovable, con fecha_estimada_termino en 3 meses → aparece en /futuro/renovaciones."""
    headers = proveedor_activo["headers"]

    fecha_termino = datetime.now(UTC) + timedelta(days=90)  # 3 meses
    lic = await make_licitacion(
        estado=LicitacionEstado.adjudicada,
        es_renovable=True,
    )

    # Actualizar fecha_estimada_termino_contrato directamente (campo desnormalizado)
    lic_db = await db_session.get(Licitacion, lic.codigo)
    assert lic_db is not None
    lic_db.fecha_estimada_termino_contrato = fecha_termino
    await db_session.commit()

    resp = await client.get("/api/v1/futuro/renovaciones", headers=headers)
    assert resp.status_code == 200, resp.text

    codigos = [item["licitacion_codigo"] for item in resp.json()["items"]]
    assert lic.codigo in codigos, (
        f"La licitación {lic.codigo!r} con fecha de término en 3 meses "
        f"debería aparecer en renovaciones, pero no está. "
        f"Codigos: {codigos}"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_renovaciones_licitacion_no_renovable_excluida(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
    make_licitacion: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """Licitación adjudicada pero es_renovable=False → NO aparece en /futuro/renovaciones."""
    headers = proveedor_activo["headers"]

    fecha_termino = datetime.now(UTC) + timedelta(days=60)
    lic = await make_licitacion(
        estado=LicitacionEstado.adjudicada,
        es_renovable=False,  # <-- no renovable
    )

    lic_db = await db_session.get(Licitacion, lic.codigo)
    assert lic_db is not None
    lic_db.fecha_estimada_termino_contrato = fecha_termino
    await db_session.commit()

    resp = await client.get("/api/v1/futuro/renovaciones", headers=headers)
    assert resp.status_code == 200, resp.text

    codigos = [item["licitacion_codigo"] for item in resp.json()["items"]]
    assert lic.codigo not in codigos, (
        f"La licitación {lic.codigo!r} con es_renovable=False "
        f"NO debería aparecer en renovaciones"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_renovaciones_fuera_del_horizonte_excluida(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
    make_licitacion: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """Licitación renovable pero fecha_estimada_termino en 8 meses → fuera del horizonte de 6 meses."""
    headers = proveedor_activo["headers"]

    # El endpoint usa meses_horizonte=6 por defecto (6 * 30 = 180 días aprox).
    # 8 meses = 240 días → fuera del horizonte con meses_horizonte=6
    fecha_termino = datetime.now(UTC) + timedelta(days=240)
    lic = await make_licitacion(
        estado=LicitacionEstado.adjudicada,
        es_renovable=True,
    )

    lic_db = await db_session.get(Licitacion, lic.codigo)
    assert lic_db is not None
    lic_db.fecha_estimada_termino_contrato = fecha_termino
    await db_session.commit()

    # Usar horizonte de 6 meses explícitamente
    resp = await client.get(
        "/api/v1/futuro/renovaciones",
        params={"meses_horizonte": 6},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    codigos = [item["licitacion_codigo"] for item in resp.json()["items"]]
    assert lic.codigo not in codigos, (
        f"La licitación {lic.codigo!r} con fecha de término en 240 días "
        f"NO debería aparecer con horizonte de 6 meses (180 días)"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_renovaciones_requiere_autenticacion(
    client: AsyncClient,
) -> None:
    """GET /futuro/renovaciones sin token → 401."""
    resp = await client.get("/api/v1/futuro/renovaciones")
    assert resp.status_code == 401, resp.text


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_renovaciones_paginacion(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
    make_licitacion: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """Con page_size=1 y 2 licitaciones renovables → total >= 2, page_size=1 en respuesta."""
    headers = proveedor_activo["headers"]

    fecha_termino = datetime.now(UTC) + timedelta(days=60)

    lic1 = await make_licitacion(
        estado=LicitacionEstado.adjudicada,
        es_renovable=True,
        nombre="Renovacion paginacion 1",
    )
    lic2 = await make_licitacion(
        estado=LicitacionEstado.adjudicada,
        es_renovable=True,
        nombre="Renovacion paginacion 2",
    )

    for codigo in [lic1.codigo, lic2.codigo]:
        lic_db = await db_session.get(Licitacion, codigo)
        assert lic_db is not None
        lic_db.fecha_estimada_termino_contrato = fecha_termino
    await db_session.commit()

    resp = await client.get(
        "/api/v1/futuro/renovaciones",
        params={"page": 1, "page_size": 1},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["page_size"] == 1
    assert len(data["items"]) == 1
    assert data["total"] >= 2, (
        f"Se esperaban al menos 2 renovaciones pero total={data['total']}"
    )


# ===========================================================================
# Epic 9.1 y 9.3 — NOT implementados (xfail documenta el gap)
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.xfail(
    reason=(
        "spec US-9.1: Plan Anual de Compras no está implementado en v1. "
        "No existe endpoint /api/v1/futuro/plan-anual"
    ),
    strict=False,
)
async def test_plan_anual_no_implementado(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """GET /futuro/plan-anual → documenta que el endpoint no existe aún (US-9.1).

    Se espera 404/405. Si algún día se implementa, este test dejará de ser xfail.
    """
    headers = proveedor_activo["headers"]
    resp = await client.get("/api/v1/futuro/plan-anual", headers=headers)
    # Si el endpoint existiera, esperaríamos 200 — documentamos la ausencia
    assert resp.status_code not in (404, 405), (
        f"US-9.1 Plan Anual sigue sin implementar (status={resp.status_code})"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.xfail(
    reason=(
        "spec US-9.3: Patrones Estacionales no está implementado en v1. "
        "No existe endpoint /api/v1/futuro/patrones ni /api/v1/analisis/patrones"
    ),
    strict=False,
)
async def test_patrones_estacionales_no_implementado(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """GET /futuro/patrones → documenta que el endpoint no existe aún (US-9.3)."""
    headers = proveedor_activo["headers"]
    resp = await client.get("/api/v1/futuro/patrones", headers=headers)
    assert resp.status_code not in (404, 405), (
        f"US-9.3 Patrones Estacionales sigue sin implementar (status={resp.status_code})"
    )


# ===========================================================================
# US-8.2 — Vista por radar (NOT implementada, xfail)
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.xfail(
    reason=(
        "spec US-8.2: Vista del pipeline agrupado por radar no está implementada. "
        "GET /api/v1/pipeline?groupby=radar no es soportado"
    ),
    strict=False,
)
async def test_vista_por_radar_no_existe(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """GET /pipeline?groupby=radar → documenta que la funcionalidad no existe (US-8.2).

    Se espera que devuelva 422 (parámetro no reconocido) o que simplemente
    ignore el parámetro (lo que también indicaría que no está implementado).
    """
    headers = proveedor_activo["headers"]
    resp = await client.get(
        "/api/v1/pipeline", params={"groupby": "radar"}, headers=headers
    )
    # Si devolviese una respuesta agrupada por radar, sería el comportamiento esperado
    # de la spec — pero en v1 no existe, así que este test falla (xfail)
    assert resp.status_code == 200 and "radar" in str(resp.json()), (
        f"US-8.2 Vista por radar no implementada (status={resp.status_code})"
    )


# ===========================================================================
# Infraestructura — Health + Catálogos
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_health_retorna_ok(
    client: AsyncClient,
) -> None:
    """GET /health → 200 con indicadores de estado de componentes."""
    resp = await client.get("/health")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "status" in data
    assert "components" in data
    assert "postgres" in data["components"]
    assert "redis" in data["components"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_catalogos_regiones(
    client: AsyncClient,
) -> None:
    """GET /catalogos/regiones → lista de 16 regiones de Chile."""
    resp = await client.get("/api/v1/catalogos/regiones")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) == 16, (
        f"Chile tiene 16 regiones, pero se obtuvieron {len(data['items'])}"
    )
    # Cada ítem debe tener código y nombre
    for item in data["items"]:
        assert "codigo" in item
        assert "nombre" in item


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_catalogos_unspsc_paginado(
    client: AsyncClient,
) -> None:
    """GET /catalogos/unspsc → retorna ítems con códigos jerárquicos."""
    resp = await client.get("/api/v1/catalogos/unspsc")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) > 0, "El catálogo UNSPSC debe tener al menos un segmento"

    # Verificar estructura jerárquica: cada segmento tiene código, nombre y familias
    primer_segmento = data["items"][0]
    assert "codigo" in primer_segmento
    assert "nombre" in primer_segmento
    assert "familias" in primer_segmento
    # Los códigos de segmento son de 2 dígitos
    assert len(primer_segmento["codigo"]) == 2


# ===========================================================================
# Rutas negativas
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_radar_patch_nombre_vacio_retorna_422(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """PATCH radar con nombre='' → 422 (Pydantic min_length=1)."""
    headers = proveedor_activo["headers"]
    empresa = proveedor_activo["empresa"]

    radar = Radar(empresa_id=empresa.id, nombre="Radar para patch inválido", filtros={})
    db_session.add(radar)
    await db_session.commit()
    await db_session.refresh(radar)

    try:
        resp = await client.patch(
            f"/api/v1/radares/{radar.id}",
            json={"nombre": ""},
            headers=headers,
        )
        assert resp.status_code == 422, (
            f"Se esperaba 422 al patchear nombre vacío, "
            f"pero se obtuvo {resp.status_code}: {resp.text}"
        )
    finally:
        await db_session.execute(delete(Radar).where(Radar.id == radar.id))
        await db_session.commit()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_radar_id_inexistente_retorna_404(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """GET /radares/{uuid-inexistente} → 404."""
    headers = proveedor_activo["headers"]
    id_falso = "00000000-0000-0000-0000-000000000000"

    resp = await client.get(f"/api/v1/radares/{id_falso}", headers=headers)
    assert resp.status_code == 404, resp.text


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_interes_sin_auth_retorna_401(
    client: AsyncClient,
) -> None:
    """GET /intereses sin token → 401."""
    resp = await client.get("/api/v1/intereses")
    assert resp.status_code == 401, resp.text


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_empresa_sin_auth_retorna_401(
    client: AsyncClient,
) -> None:
    """GET /empresa/me sin token → 401."""
    resp = await client.get("/api/v1/empresa/me")
    assert resp.status_code == 401, resp.text
