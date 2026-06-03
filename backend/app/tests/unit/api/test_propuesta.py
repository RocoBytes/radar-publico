"""Tests unitarios para los endpoints de propuesta técnica.

GET  /api/v1/licitaciones/{codigo}/propuesta
POST /api/v1/licitaciones/{codigo}/propuesta
GET  /api/v1/licitaciones/{codigo}/propuesta/export

Valida: autenticación, aislamiento entre empresas, estados del workflow,
delegación correcta a Celery (send_task) y exportación DOCX.

Usa BD real de test (NullPool — conftest patch_db_session) + AsyncClient ASGI.
send_task se parchea con unittest.mock para no requerir broker activo.

Nota de diseño: cada test usa su propia sesión de AsyncSessionLocal para
evitar que el estado de sesión de un test afecte a los siguientes. El
`db_session` del conftest se reserva para la fixture de cleanup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.core.security import create_access_token
from app.db import session as _db_session_module
from app.models.analisis_ia import AnalisisBases, BorradorPropuesta
from app.models.empresa import Empresa
from app.models.enums import AnalisisStatus, LicitacionEstado
from app.models.licitacion import Licitacion

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid() -> str:
    return uuid.uuid4().hex[:6]


def _auth_headers(user_id: Any) -> dict[str, str]:
    token = create_access_token(subject=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def _codigo_lic() -> str:
    return f"PROP-{_uid()}-T26"


def _make_licitacion(codigo: str) -> Licitacion:
    return Licitacion(
        codigo=codigo,
        nombre=f"Licitacion propuesta test {codigo}",
        estado=LicitacionEstado.publicada,
        moneda="CLP",
    )


def _make_analisis(
    licitacion_codigo: str,
    status: AnalisisStatus = AnalisisStatus.listo,
) -> AnalisisBases:
    return AnalisisBases(
        licitacion_codigo=licitacion_codigo,
        version=1,
        status=status,
    )


def _make_borrador(
    licitacion_codigo: str,
    empresa_id: uuid.UUID,
    status: AnalisisStatus = AnalisisStatus.listo,
) -> BorradorPropuesta:
    return BorradorPropuesta(
        licitacion_codigo=licitacion_codigo,
        empresa_id=empresa_id,
        version=1,
        status=status,
        titulo="Propuesta Test",
        secciones=[{"titulo": "Introducción", "contenido": "Contenido test"}],
    )


async def _get_empresa_id(user_id: uuid.UUID) -> uuid.UUID:
    """Obtiene el id de la empresa del usuario usando una sesión fresca."""
    async with _db_session_module.AsyncSessionLocal() as s:
        result = await s.execute(select(Empresa).where(Empresa.usuario_id == user_id))
        empresa = result.scalar_one()
        return empresa.id


async def _insertar_lic(codigo: str) -> None:
    """Inserta una licitacion en una sesión propia y la commitea."""
    async with _db_session_module.AsyncSessionLocal() as s:
        s.add(_make_licitacion(codigo))
        await s.commit()


async def _insertar_analisis(licitacion_codigo: str, status: AnalisisStatus) -> None:
    """Inserta un AnalisisBases en una sesión propia."""
    async with _db_session_module.AsyncSessionLocal() as s:
        s.add(_make_analisis(licitacion_codigo, status))
        await s.commit()


async def _insertar_borrador(
    licitacion_codigo: str,
    empresa_id: uuid.UUID,
    status: AnalisisStatus,
) -> None:
    """Inserta un BorradorPropuesta en una sesión propia."""
    async with _db_session_module.AsyncSessionLocal() as s:
        s.add(_make_borrador(licitacion_codigo, empresa_id, status))
        await s.commit()


# ---------------------------------------------------------------------------
# Fixtures de limpieza
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def limpiar_datos(db_session: AsyncSession) -> None:
    """Limpia borradores, análisis y licitaciones antes de cada test."""
    await db_session.execute(delete(BorradorPropuesta))
    await db_session.execute(delete(AnalisisBases))
    await db_session.execute(delete(Licitacion))
    await db_session.commit()


# ===========================================================================
# GET /propuesta
# ===========================================================================


# Caso 1: sin autenticación → 401
@pytest.mark.asyncio
async def test_get_propuesta_sin_auth_retorna_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/licitaciones/CUALQUIER/propuesta")
    assert resp.status_code == 401


# Caso 2: no hay borrador → 404 con mención a POST
@pytest.mark.asyncio
async def test_get_propuesta_sin_borrador_retorna_404(
    client: AsyncClient,
    make_user: Any,
) -> None:
    user = await make_user(email=f"u{_uid()}@test.cl")
    codigo = _codigo_lic()
    await _insertar_lic(codigo)

    resp = await client.get(
        f"/api/v1/licitaciones/{codigo}/propuesta",
        headers=_auth_headers(user.id),
    )
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert "POST" in detail, f"El mensaje 404 debe mencionar POST, mensaje: {detail!r}"


# Caso 3: borrador existe para la empresa → 200 con datos del borrador
@pytest.mark.asyncio
async def test_get_propuesta_con_borrador_retorna_200(
    client: AsyncClient,
    make_user: Any,
) -> None:
    user = await make_user(email=f"u{_uid()}@test.cl")
    codigo = _codigo_lic()
    empresa_id = await _get_empresa_id(user.id)

    await _insertar_lic(codigo)
    await _insertar_borrador(codigo, empresa_id, AnalisisStatus.listo)

    resp = await client.get(
        f"/api/v1/licitaciones/{codigo}/propuesta",
        headers=_auth_headers(user.id),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["licitacion_codigo"] == codigo
    assert data["status"] == "listo"
    assert data["titulo"] == "Propuesta Test"


# Caso 4: borrador existe para OTRA empresa → 404 (aislamiento)
@pytest.mark.asyncio
async def test_get_propuesta_borrador_otra_empresa_retorna_404(
    client: AsyncClient,
    make_user: Any,
) -> None:
    """El borrador de otra empresa no es visible: aislamiento por empresa_id."""
    user_a = await make_user(email=f"ua{_uid()}@test.cl", rut=f"76.{_uid()}-K")
    user_b = await make_user(email=f"ub{_uid()}@test.cl", rut=f"77.{_uid()}-9")
    codigo = _codigo_lic()
    empresa_id_a = await _get_empresa_id(user_a.id)

    await _insertar_lic(codigo)
    # Borrador pertenece a empresa_a
    await _insertar_borrador(codigo, empresa_id_a, AnalisisStatus.listo)

    # user_b consulta → debe ver 404 porque su empresa no tiene borrador
    resp = await client.get(
        f"/api/v1/licitaciones/{codigo}/propuesta",
        headers=_auth_headers(user_b.id),
    )
    assert (
        resp.status_code == 404
    ), f"user_b no debe ver el borrador de user_a, obtenido: {resp.status_code}"


# ===========================================================================
# POST /propuesta
# ===========================================================================


# Caso 5: sin autenticación → 401
@pytest.mark.asyncio
async def test_post_propuesta_sin_auth_retorna_401(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/licitaciones/CUALQUIER/propuesta")
    assert resp.status_code == 401


# Caso 6: licitación no encontrada → 404
@pytest.mark.asyncio
async def test_post_propuesta_licitacion_inexistente_retorna_404(
    client: AsyncClient,
    make_user: Any,
) -> None:
    user = await make_user(email=f"u{_uid()}@test.cl")
    resp = await client.post(
        "/api/v1/licitaciones/NO-EXISTE-JAMAS/propuesta",
        headers=_auth_headers(user.id),
    )
    assert resp.status_code == 404


# Caso 7: sin análisis listo → 422
@pytest.mark.asyncio
async def test_post_propuesta_sin_analisis_listo_retorna_422(
    client: AsyncClient,
    make_user: Any,
) -> None:
    """Sin AnalisisBases con status=listo → 422 UNPROCESSABLE_ENTITY."""
    user = await make_user(email=f"u{_uid()}@test.cl")
    codigo = _codigo_lic()
    await _insertar_lic(codigo)
    # Análisis existe pero está pendiente, no listo
    await _insertar_analisis(codigo, AnalisisStatus.pendiente)

    resp = await client.post(
        f"/api/v1/licitaciones/{codigo}/propuesta",
        headers=_auth_headers(user.id),
    )
    assert resp.status_code == 422


# Caso 8: análisis listo → 202 "encolado", send_task llamado con args correctos
@pytest.mark.asyncio
async def test_post_propuesta_analisis_listo_encola_tarea(
    client: AsyncClient,
    make_user: Any,
) -> None:
    """Análisis listo + sin borrador previo → 202 status=encolado, send_task llamado."""
    user = await make_user(email=f"u{_uid()}@test.cl")
    codigo = _codigo_lic()
    empresa_id = await _get_empresa_id(user.id)

    await _insertar_lic(codigo)
    await _insertar_analisis(codigo, AnalisisStatus.listo)

    with patch("app.celery_app.celery_app.send_task") as mock_send:
        resp = await client.post(
            f"/api/v1/licitaciones/{codigo}/propuesta",
            headers=_auth_headers(user.id),
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "encolado", f"Esperado 'encolado', obtenido: {data['status']}"

    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert (
        call_args[0][0] == "tasks.generar_borrador.generar_borrador_propuesta"
    ), f"Nombre de tarea incorrecto: {call_args[0][0]!r}"
    task_args = call_args[1]["args"] if "args" in call_args[1] else call_args[0][1]
    assert task_args[0] == codigo, f"Primer arg debe ser el codigo: {task_args}"
    assert task_args[1] == str(
        empresa_id
    ), f"Segundo arg debe ser str(empresa.id)={str(empresa_id)!r}, obtenido: {task_args[1]!r}"


# Caso 9: borrador ya procesando → 202 "en_proceso", send_task NO llamado
@pytest.mark.asyncio
async def test_post_propuesta_borrador_procesando_no_reencola(
    client: AsyncClient,
    make_user: Any,
) -> None:
    """Borrador en estado procesando → 202 status=en_proceso, send_task NO se llama."""
    user = await make_user(email=f"u{_uid()}@test.cl")
    codigo = _codigo_lic()
    empresa_id = await _get_empresa_id(user.id)

    await _insertar_lic(codigo)
    await _insertar_analisis(codigo, AnalisisStatus.listo)
    await _insertar_borrador(codigo, empresa_id, AnalisisStatus.procesando)

    with patch("app.celery_app.celery_app.send_task") as mock_send:
        resp = await client.post(
            f"/api/v1/licitaciones/{codigo}/propuesta",
            headers=_auth_headers(user.id),
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "en_proceso", f"Esperado 'en_proceso', obtenido: {data['status']}"
    mock_send.assert_not_called()


# Caso 10: borrador ya listo → 202 "listo", send_task NO llamado
@pytest.mark.asyncio
async def test_post_propuesta_borrador_listo_no_reencola(
    client: AsyncClient,
    make_user: Any,
) -> None:
    """Borrador en estado listo → 202 status=listo, send_task NO se llama."""
    user = await make_user(email=f"u{_uid()}@test.cl")
    codigo = _codigo_lic()
    empresa_id = await _get_empresa_id(user.id)

    await _insertar_lic(codigo)
    await _insertar_analisis(codigo, AnalisisStatus.listo)
    await _insertar_borrador(codigo, empresa_id, AnalisisStatus.listo)

    with patch("app.celery_app.celery_app.send_task") as mock_send:
        resp = await client.post(
            f"/api/v1/licitaciones/{codigo}/propuesta",
            headers=_auth_headers(user.id),
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "listo", f"Esperado 'listo', obtenido: {data['status']}"
    mock_send.assert_not_called()


# ===========================================================================
# GET /propuesta/export
# ===========================================================================


# Caso 11: sin autenticación → 401
@pytest.mark.asyncio
async def test_export_propuesta_sin_auth_retorna_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/licitaciones/CUALQUIER/propuesta/export")
    assert resp.status_code == 401


# Caso 12: sin borrador listo → 404
@pytest.mark.asyncio
async def test_export_propuesta_sin_borrador_retorna_404(
    client: AsyncClient,
    make_user: Any,
) -> None:
    user = await make_user(email=f"u{_uid()}@test.cl")
    codigo = _codigo_lic()
    await _insertar_lic(codigo)

    resp = await client.get(
        f"/api/v1/licitaciones/{codigo}/propuesta/export",
        headers=_auth_headers(user.id),
    )
    assert resp.status_code == 404


# Caso 13: borrador existe pero está procesando → 404 (no listo)
@pytest.mark.asyncio
async def test_export_propuesta_borrador_procesando_retorna_404(
    client: AsyncClient,
    make_user: Any,
) -> None:
    """Borrador con status=procesando no está disponible para exportar → 404."""
    user = await make_user(email=f"u{_uid()}@test.cl")
    codigo = _codigo_lic()
    empresa_id = await _get_empresa_id(user.id)

    await _insertar_lic(codigo)
    await _insertar_borrador(codigo, empresa_id, AnalisisStatus.procesando)

    resp = await client.get(
        f"/api/v1/licitaciones/{codigo}/propuesta/export",
        headers=_auth_headers(user.id),
    )
    assert (
        resp.status_code == 404
    ), f"Borrador procesando debe retornar 404, obtenido: {resp.status_code}"


# Caso 14: borrador listo → 200 con Content-Type DOCX y filename correcto
@pytest.mark.asyncio
async def test_export_propuesta_borrador_listo_retorna_docx(
    client: AsyncClient,
    make_user: Any,
) -> None:
    """Borrador con status=listo → 200, Content-Type docx, filename con el código."""
    user = await make_user(email=f"u{_uid()}@test.cl")
    codigo = _codigo_lic()
    empresa_id = await _get_empresa_id(user.id)

    await _insertar_lic(codigo)
    await _insertar_borrador(codigo, empresa_id, AnalisisStatus.listo)

    resp = await client.get(
        f"/api/v1/licitaciones/{codigo}/propuesta/export",
        headers=_auth_headers(user.id),
    )
    assert resp.status_code == 200, f"Esperado 200, obtenido: {resp.status_code}"

    content_type = resp.headers.get("content-type", "")
    assert (
        "officedocument.wordprocessingml.document" in content_type
    ), f"Content-Type debe ser DOCX, obtenido: {content_type!r}"

    content_disposition = resp.headers.get("content-disposition", "")
    assert f"propuesta-{codigo}.docx" in content_disposition, (
        f"Content-Disposition debe contener 'propuesta-{codigo}.docx', "
        f"obtenido: {content_disposition!r}"
    )

    # El cuerpo debe ser un DOCX válido (ZIP con magic bytes PK)
    body = resp.content
    assert len(body) > 0, "El cuerpo de la respuesta no debe estar vacío"
    assert body[:4] == b"PK\x03\x04", (
        f"Los primeros 4 bytes deben ser el magic ZIP/DOCX 'PK\\x03\\x04', "
        f"obtenido: {body[:4]!r}"
    )
