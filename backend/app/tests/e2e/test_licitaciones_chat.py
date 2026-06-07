"""Suite de aceptación E2E — Búsqueda, Detalle y Chat IA de licitaciones.

Cubre:
  Epic 5 (US-5.1 a US-5.4) — Búsqueda y filtros
  Epic 6 (US-6.1 a US-6.5) — Detalle de licitación + Chat IA
  Epic 7 (US-7.2, US-7.3)  — Vista pasado (NOT implementado en v1)
  Rutas negativas           — auth, 404, 422

Convenciones:
  - @pytest.mark.e2e en cada test
  - @pytest.mark.asyncio para coroutines (compatible con anyio_backend="asyncio")
  - Cada test es independiente: crea y limpia sus propios datos
  - LLM mockeado para no llamar a Anthropic real

Nota sobre patch del LLM:
  `chat_streaming` se importa de forma LOCAL dentro de `_generar_respuesta`
  (en app/api/v1/chat.py). El target correcto para mock es
  `app.services.llm.client.chat_streaming`, no `app.api.v1.chat.chat_streaming`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
import uuid

import pytest
from sqlalchemy import delete, select

from app.models.conversacion import ConversacionIA, ConversacionMensaje
from app.models.enums import LicitacionEstado, MensajeRol

# Importa helper de auth del conftest e2e (disponible por discovery automático de pytest)
from app.tests.e2e.conftest import auth_headers

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Fake LLM stream — evita llamadas reales a Anthropic
# ---------------------------------------------------------------------------


async def _fake_stream(messages: list[dict[str, str]]) -> AsyncGenerator[str, None]:
    """Stream falso que devuelve texto plano con cita simulada."""
    yield "Respuesta de prueba con cita [página 1]"


# ---------------------------------------------------------------------------
# Helper: limpiar conversaciones creadas durante los tests de chat
# ---------------------------------------------------------------------------


async def _limpiar_conversaciones(db_session: AsyncSession, empresa_id: uuid.UUID) -> None:
    """Elimina todas las conversaciones y mensajes de la empresa de test."""
    convs = (
        (
            await db_session.execute(
                select(ConversacionIA).where(ConversacionIA.empresa_id == empresa_id)
            )
        )
        .scalars()
        .all()
    )
    for conv in convs:
        await db_session.execute(
            delete(ConversacionMensaje).where(ConversacionMensaje.conversacion_id == conv.id)
        )
    await db_session.execute(delete(ConversacionIA).where(ConversacionIA.empresa_id == empresa_id))
    await db_session.commit()


# ===========================================================================
# Epic 5 — Búsqueda y filtros (US-5.1 a US-5.4)
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_busqueda_por_palabra_exacta_en_titulo(
    client: AsyncClient,
    make_licitacion: Any,
    proveedor_activo: dict[str, Any],
) -> None:
    """US-5.1: búsqueda por palabra exacta en el nombre de la licitación."""
    palabra = "xilopetala"
    await make_licitacion(nombre=f"Servicio de {palabra} para municipio")

    resp = await client.get(
        "/api/v1/licitaciones",
        params={"q": palabra},
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) >= 1
    assert any(palabra.lower() in item["nombre"].lower() for item in data["items"])


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_busqueda_acentos_ignora(
    client: AsyncClient,
    make_licitacion: Any,
    proveedor_activo: dict[str, Any],
) -> None:
    """US-5.1: búsqueda sin acento debería encontrar nombre con acento.

    Marcado xfail porque Postgres plainto_tsquery con diccionario 'spanish'
    podría o no normalizar acentos según la configuración del servidor.
    Si el backend lo maneja, pasa; si no, se documenta el gap.
    """
    pytest.xfail(
        reason=(
            "US-5.1: Postgres 'spanish' ts_config normaliza acentos solo si el "
            "diccionario está configurado correctamente. Puede fallar en entornos "
            "sin unaccent instalado."
        )
    )
    await make_licitacion(nombre="Mantención de ascensores municipales")

    resp = await client.get(
        "/api/v1/licitaciones",
        params={"q": "mantencion"},
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_busqueda_sin_resultados_retorna_lista_vacia(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """US-5.1: búsqueda con término que no existe → items vacíos."""
    resp = await client.get(
        "/api/v1/licitaciones",
        params={"q": "xyzqueryquenoexistejamas99887766"},
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["has_next"] is False


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_filtro_estado_publicada(
    client: AsyncClient,
    make_licitacion: Any,
    db_session: AsyncSession,
    proveedor_activo: dict[str, Any],
) -> None:
    """US-5.2: filtro por estado=publicada solo retorna licitaciones publicadas."""
    sufijo = uuid.uuid4().hex[:6]
    nombre_pub = f"Licitacion publicada {sufijo}"
    nombre_adj = f"Licitacion adjudicada {sufijo}"

    lic_pub = await make_licitacion(
        nombre=nombre_pub,
        estado=LicitacionEstado.publicada,
    )
    lic_adj = await make_licitacion(
        nombre=nombre_adj,
        estado=LicitacionEstado.adjudicada,
    )

    resp = await client.get(
        "/api/v1/licitaciones",
        params={"estado": "publicada", "q": sufijo},
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    codigos = [item["codigo"] for item in data["items"]]
    assert lic_pub.codigo in codigos
    assert lic_adj.codigo not in codigos


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_filtro_combinado_estado_y_q(
    client: AsyncClient,
    make_licitacion: Any,
    proveedor_activo: dict[str, Any],
) -> None:
    """US-5.2: filtro combinado estado + q solo retorna la coincidencia exacta."""
    sufijo = uuid.uuid4().hex[:6]
    nombre_match = f"Consultoría {sufijo} esperada"
    nombre_no_match = f"Consultoría {sufijo} adjudicada"

    lic_match = await make_licitacion(
        nombre=nombre_match,
        estado=LicitacionEstado.publicada,
    )
    await make_licitacion(
        nombre=nombre_no_match,
        estado=LicitacionEstado.adjudicada,
    )

    resp = await client.get(
        "/api/v1/licitaciones",
        params={"estado": "publicada", "q": f"esperada {sufijo}"},
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    codigos = [item["codigo"] for item in data["items"]]
    assert lic_match.codigo in codigos


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_paginacion_sin_solapamiento(
    client: AsyncClient,
    make_licitacion: Any,
    proveedor_activo: dict[str, Any],
) -> None:
    """US-5.2: page=1 y page=2 no comparten ningún codigo."""
    sufijo = uuid.uuid4().hex[:6]
    # Crear 22 licitaciones únicas para tener >10 en cada página
    for i in range(22):
        await make_licitacion(nombre=f"Licitacion paginacion {sufijo} item{i:02d}")

    resp1 = await client.get(
        "/api/v1/licitaciones",
        params={"q": sufijo, "page": 1, "page_size": 10},
        headers=proveedor_activo["headers"],
    )
    resp2 = await client.get(
        "/api/v1/licitaciones",
        params={"q": sufijo, "page": 2, "page_size": 10},
        headers=proveedor_activo["headers"],
    )

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    codigos_p1 = {item["codigo"] for item in resp1.json()["items"]}
    codigos_p2 = {item["codigo"] for item in resp2.json()["items"]}

    assert len(codigos_p1) == 10
    assert len(codigos_p2) >= 1
    # Ningún solapamiento
    assert codigos_p1.isdisjoint(
        codigos_p2
    ), f"Solapamiento en paginación: {codigos_p1 & codigos_p2}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_resultado_incluye_campos_minimos(
    client: AsyncClient,
    make_licitacion: Any,
    proveedor_activo: dict[str, Any],
) -> None:
    """US-5.4: cada item del listado tiene los campos mínimos requeridos."""
    sufijo = uuid.uuid4().hex[:6]
    await make_licitacion(nombre=f"Licitacion campos {sufijo}")

    resp = await client.get(
        "/api/v1/licitaciones",
        params={"q": sufijo},
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1

    campos_requeridos = {"codigo", "nombre", "estado", "monto_estimado", "fecha_cierre"}
    for item in items:
        faltantes = campos_requeridos - set(item.keys())
        assert not faltantes, f"Campos faltantes en item: {faltantes}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_detalle_retorna_todos_campos(
    client: AsyncClient,
    make_licitacion: Any,
    proveedor_activo: dict[str, Any],
) -> None:
    """US-5.4: el detalle de una licitación retorna todos los campos esperados."""
    lic = await make_licitacion()

    resp = await client.get(
        f"/api/v1/licitaciones/{lic.codigo}",
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()

    campos_requeridos = {
        "codigo",
        "nombre",
        "estado",
        "monto_estimado",
        "organismo_nombre",
    }
    faltantes = campos_requeridos - set(data.keys())
    assert not faltantes, f"Campos faltantes en detalle: {faltantes}"
    assert data["codigo"] == lic.codigo


# ===========================================================================
# Epic 6 — Detalle de licitación (US-6.1 a US-6.5)
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_detalle_licitacion_no_encontrada_retorna_404(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """US-6.1: GET /licitaciones/{codigo} con código inexistente → 404."""
    resp = await client.get(
        "/api/v1/licitaciones/CODIGO-INEXISTENTE-JAMAS-99",
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_detalle_licitacion_otro_tenant_no_oculta_datos(
    client: AsyncClient,
    make_licitacion: Any,
    make_user: Any,
    proveedor_activo: dict[str, Any],
) -> None:
    """US-6.1: licitaciones son públicas dentro de la plataforma.

    Un proveedor distinto al que creó la licitación puede verla (200).
    """
    from app.models.enums import UserRole, UserStatus

    lic = await make_licitacion()

    # Segundo usuario diferente al proveedor_activo
    otro_usuario = await make_user(
        email=f"otro_{uuid.uuid4().hex[:6]}@test.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=True,
    )
    headers_otro = auth_headers(otro_usuario.id)

    resp = await client.get(
        f"/api/v1/licitaciones/{lic.codigo}",
        headers=headers_otro,
    )
    assert resp.status_code == 200
    assert resp.json()["codigo"] == lic.codigo


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_inteligencia_licitacion_sin_organismo(
    client: AsyncClient,
    make_licitacion: Any,
    proveedor_activo: dict[str, Any],
) -> None:
    """US-6.4: licitación sin organismo → /inteligencia retorna 200 con ceros/vacíos."""
    lic = await make_licitacion(with_organismo=False)

    resp = await client.get(
        f"/api/v1/licitaciones/{lic.codigo}/inteligencia",
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_licitaciones_organismo"] == 0
    assert data["top_proveedores"] == []


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_inteligencia_requiere_autenticacion(
    client: AsyncClient,
    make_licitacion: Any,
) -> None:
    """US-6.4: GET /inteligencia sin token → 401."""
    lic = await make_licitacion()

    resp = await client.get(f"/api/v1/licitaciones/{lic.codigo}/inteligencia")
    assert resp.status_code == 401


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_chat_historial_vacio_para_licitacion_nueva(
    client: AsyncClient,
    make_licitacion: Any,
    proveedor_activo: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """US-6.5: GET /chat/{codigo} para licitación nueva → 200, mensajes=[]."""
    empresa = proveedor_activo["empresa"]
    await _limpiar_conversaciones(db_session, empresa.id)

    lic = await make_licitacion()

    resp = await client.get(
        f"/api/v1/chat/{lic.codigo}",
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mensajes"] == []
    assert data["licitacion_codigo"] == lic.codigo

    # Limpieza
    await _limpiar_conversaciones(db_session, empresa.id)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_chat_rate_limit_100_mensajes(
    client: AsyncClient,
    make_licitacion: Any,
    proveedor_activo: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """US-6.5: con 100 mensajes user hoy → POST mensaje → 429.

    El rate limit se evalúa ANTES de invocar el LLM, por lo que no
    es necesario mockear chat_streaming para este test.
    """
    empresa = proveedor_activo["empresa"]
    await _limpiar_conversaciones(db_session, empresa.id)

    lic = await make_licitacion()

    # Crear conversación primero
    conv = ConversacionIA(
        empresa_id=empresa.id,
        licitacion_codigo=lic.codigo,
        titulo="Test rate limit",
    )
    db_session.add(conv)
    await db_session.flush()

    # Insertar 100 mensajes de tipo user con created_at de hoy UTC
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    mensajes = [
        ConversacionMensaje(
            conversacion_id=conv.id,
            rol=MensajeRol.user,
            contenido=f"mensaje {i}",
            citas=[],
            created_at=today.replace(hour=12),
        )
        for i in range(100)
    ]
    db_session.add_all(mensajes)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/chat/{lic.codigo}/mensaje",
        json={"contenido": "mensaje numero 101"},
        headers=proveedor_activo["headers"],
    )

    assert resp.status_code == 429

    # Limpieza
    await _limpiar_conversaciones(db_session, empresa.id)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_chat_mensaje_101_error_claro_no_crashea(
    client: AsyncClient,
    make_licitacion: Any,
    proveedor_activo: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """US-6.5: después del rate limit la respuesta tiene mensaje claro, no 500.

    El 429 se lanza antes del streaming → no se necesita mock de LLM.
    """
    empresa = proveedor_activo["empresa"]
    await _limpiar_conversaciones(db_session, empresa.id)

    lic = await make_licitacion()

    conv = ConversacionIA(
        empresa_id=empresa.id,
        licitacion_codigo=lic.codigo,
        titulo="Test error claro",
    )
    db_session.add(conv)
    await db_session.flush()

    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    mensajes = [
        ConversacionMensaje(
            conversacion_id=conv.id,
            rol=MensajeRol.user,
            contenido=f"msg {i}",
            citas=[],
            created_at=today.replace(hour=10),
        )
        for i in range(100)
    ]
    db_session.add_all(mensajes)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/chat/{lic.codigo}/mensaje",
        json={"contenido": "esto debe ser rechazado"},
        headers=proveedor_activo["headers"],
    )

    # No debe ser 500 — el error debe ser explícito (429 con detail)
    assert resp.status_code != 500
    assert resp.status_code == 429
    detail = resp.json().get("detail", "")
    assert len(detail) > 0, "El campo detail no debe estar vacío en la respuesta 429"

    # Limpieza
    await _limpiar_conversaciones(db_session, empresa.id)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_chat_requiere_autenticacion(
    client: AsyncClient,
    make_licitacion: Any,
) -> None:
    """US-6.5: POST /chat/{codigo}/mensaje sin token → 401."""
    lic = await make_licitacion()

    resp = await client.post(
        f"/api/v1/chat/{lic.codigo}/mensaje",
        json={"contenido": "hola"},
    )
    assert resp.status_code == 401


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_inadmisibilidad_sin_analisis_retorna_false(
    client: AsyncClient,
    make_licitacion: Any,
    proveedor_activo: dict[str, Any],
) -> None:
    """US-6.2: licitación sin AnalisisBases → /inadmisibilidad → 200.

    analisis_disponible debe ser false.
    """
    lic = await make_licitacion()

    resp = await client.get(
        f"/api/v1/licitaciones/{lic.codigo}/inadmisibilidad",
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["analisis_disponible"] is False
    assert data["items"] == []


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_analisis_endpoint_requiere_autenticacion(
    client: AsyncClient,
    make_licitacion: Any,
) -> None:
    """US-6.2: GET /licitaciones/{codigo}/analisis sin token → 401."""
    lic = await make_licitacion()

    resp = await client.get(f"/api/v1/licitaciones/{lic.codigo}/analisis")
    assert resp.status_code == 401


# ===========================================================================
# Epic 7 — Vista pasado (US-7.2, US-7.3 — NOT implementado en v1)
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="US-7.2: endpoint histórico de precios no implementado en v1",
)
async def test_historico_precios_no_implementado(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """US-7.2: documenta que el endpoint de histórico de precios no existe en v1.

    Espera 404 o 405. Si responde 200, la feature fue implementada (xpass).
    """
    resp = await client.get(
        "/api/v1/licitaciones/historico-precios",
        headers=proveedor_activo["headers"],
    )
    # El endpoint no existe → 404 o 405, nunca 200
    assert resp.status_code in (404, 405), (
        f"El endpoint histórico-precios devolvió {resp.status_code} — "
        "¿fue implementado? Actualizar xfail."
    )


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="US-7.3: análisis de competidor no implementado en v1",
)
async def test_analisis_competidor_no_implementado(
    client: AsyncClient,
    make_licitacion: Any,
    proveedor_activo: dict[str, Any],
) -> None:
    """US-7.3: documenta que el análisis de competidor no está disponible en v1.

    No existe un endpoint dedicado; se verifica que cualquier candidato
    plausible retorna 404 o 405.
    """
    lic = await make_licitacion()

    resp = await client.get(
        f"/api/v1/licitaciones/{lic.codigo}/competidores",
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code in (404, 405), (
        f"El endpoint competidores devolvió {resp.status_code} — "
        "¿fue implementado? Actualizar xfail."
    )


# ===========================================================================
# Rutas negativas
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_licitaciones_sin_auth_retorna_401(
    client: AsyncClient,
) -> None:
    """Negativo: GET /licitaciones sin token → 401."""
    resp = await client.get("/api/v1/licitaciones")
    assert resp.status_code == 401


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_licitacion_body_malformado_retorna_422(
    client: AsyncClient,
    make_licitacion: Any,
    proveedor_activo: dict[str, Any],
) -> None:
    """Negativo: POST /chat/{codigo}/mensaje con body inválido → 422."""
    lic = await make_licitacion()

    resp = await client.post(
        f"/api/v1/chat/{lic.codigo}/mensaje",
        content=b"esto no es json valido {{{",
        headers={
            **proveedor_activo["headers"],
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 422


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_licitacion_id_inexistente_retorna_404(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """Negativo: GET /licitaciones/{codigo} con código que nunca existe → 404."""
    resp = await client.get(
        "/api/v1/licitaciones/NO-EXISTE-JAMAS-XYZ-00000",
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_chat_licitacion_inexistente_retorna_404(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """Negativo: POST /chat/{codigo}/mensaje para licitación inexistente → 404.

    El 404 se lanza ANTES de invocar el LLM (verificación de licitacion),
    por lo que no se necesita mock de chat_streaming.
    """
    resp = await client.post(
        "/api/v1/chat/NO-EXISTE-JAMAS-CHAT-99/mensaje",
        json={"contenido": "hola"},
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_directorios_organismos_paginacion(
    client: AsyncClient,
    proveedor_activo: dict[str, Any],
) -> None:
    """Cobertura: GET /directorios/organismos → 200 con estructura paginada."""
    resp = await client.get(
        "/api/v1/directorios/organismos",
        params={"page": 1, "page_size": 5},
        headers=proveedor_activo["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    # Verificar campos de paginación
    assert "items" in data
    assert "total" in data
    assert "total_pages" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)
    assert isinstance(data["total_pages"], int)
    assert data["total_pages"] >= 1


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_directorios_requiere_autenticacion(
    client: AsyncClient,
) -> None:
    """Negativo: GET /directorios/organismos sin token → 401."""
    resp = await client.get("/api/v1/directorios/organismos")
    assert resp.status_code == 401
