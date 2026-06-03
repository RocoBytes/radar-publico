"""Tests unitarios para los endpoints de empresa e intereses.

Cubre:
  GET  /api/v1/empresa/me
  PATCH /api/v1/empresa/me
  GET  /api/v1/intereses
  POST /api/v1/intereses
  DELETE /api/v1/intereses/{id}

Usa BD de test real (NullPool via conftest) con AsyncClient + ASGITransport.
Los tokens JWT se generan directamente desde app.core.security.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from httpx import AsyncClient  # noqa: TCH002
import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.core.security import create_access_token
from app.models.empresa import Empresa
from app.models.enums import UserRole, UserStatus
from app.models.interes import Interes, InteresTipo

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_headers(user_id: str) -> dict[str, str]:
    """Genera cabecera Authorization con JWT válido para el user_id dado."""
    token = create_access_token(subject=user_id)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def limpiar_intereses(db_session: AsyncSession) -> None:
    """Elimina todos los intereses antes de cada test para aislar el estado."""
    await db_session.execute(delete(Interes))
    await db_session.commit()


@pytest_asyncio.fixture
async def empresa_con_usuario(
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> tuple[Any, Empresa]:
    """Crea un usuario proveedor activo con empresa asociada.

    Retorna (usuario, empresa).
    """
    user: Any = await make_user(
        email="empresa_test@example.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        rut="76.123.456-K",
        razon_social="Empresa Test SpA",
    )
    result = await db_session.execute(select(Empresa).where(Empresa.usuario_id == user.id))
    empresa: Empresa = result.scalar_one()
    return user, empresa


@pytest_asyncio.fixture
async def segunda_empresa_con_usuario(
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> tuple[Any, Empresa]:
    """Segunda empresa independiente para tests de autorización cruzada."""
    user: Any = await make_user(
        email="empresa_segunda@example.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        rut="77.999.888-7",
        razon_social="Segunda Empresa SpA",
    )
    result = await db_session.execute(select(Empresa).where(Empresa.usuario_id == user.id))
    empresa: Empresa = result.scalar_one()
    return user, empresa


# ---------------------------------------------------------------------------
# Tests: GET /empresa/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_empresa_me_sin_auth(client: AsyncClient) -> None:
    """Sin token → 401 Unauthorized."""
    resp = await client.get("/api/v1/empresa/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_empresa_me_ok(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
) -> None:
    """Usuario con empresa → 200 con datos correctos."""
    user, empresa = empresa_con_usuario

    resp = await client.get(
        "/api/v1/empresa/me",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["rut"] == "76.123.456-K"
    assert data["razon_social"] == "Empresa Test SpA"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    # embedding nunca debe aparecer
    assert "embedding" not in data


# ---------------------------------------------------------------------------
# Tests: PATCH /empresa/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_empresa_me_ok(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
) -> None:
    """PATCH con nombre_fantasia y tamano → 200, campos actualizados."""
    user, _ = empresa_con_usuario

    resp = await client.patch(
        "/api/v1/empresa/me",
        json={"nombre_fantasia": "Mi Marca Comercial", "tamano": "pequena"},
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["nombre_fantasia"] == "Mi Marca Comercial"
    assert data["tamano"] == "pequena"
    # Campos no enviados no cambian
    assert data["rut"] == "76.123.456-K"


@pytest.mark.asyncio
async def test_patch_empresa_me_no_edita_rut(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
) -> None:
    """PATCH con rut en el body → el rut NO cambia (campo ignorado por schema)."""
    user, empresa = empresa_con_usuario
    rut_original = empresa.rut

    resp = await client.patch(
        "/api/v1/empresa/me",
        json={"rut": "99.999.999-9", "nombre_fantasia": "Intentando cambiar RUT"},
        headers=_auth_headers(str(user.id)),
    )
    # El request es válido (rut es ignorado, nombre_fantasia se aplica)
    assert resp.status_code == 200

    data = resp.json()
    # El rut debe seguir siendo el original — el schema no lo acepta
    assert data["rut"] == rut_original
    assert data["nombre_fantasia"] == "Intentando cambiar RUT"


# ---------------------------------------------------------------------------
# Tests: GET /intereses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_intereses_vacio(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
) -> None:
    """Sin intereses → lista vacía, total=0."""
    user, _ = empresa_con_usuario

    resp = await client.get(
        "/api/v1/intereses",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


# ---------------------------------------------------------------------------
# Tests: POST /intereses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_interes_ok(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
) -> None:
    """POST válido → 201 con el interés creado."""
    user, _ = empresa_con_usuario

    resp = await client.post(
        "/api/v1/intereses",
        json={"tipo": "keyword", "valor": "servicios TI", "prioridad": 7},
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 201

    data = resp.json()
    assert data["tipo"] == "keyword"
    assert data["valor"] == "servicios TI"
    assert data["prioridad"] == 7
    assert "id" in data
    assert "created_at" in data
    # embedding nunca debe aparecer
    assert "embedding" not in data


@pytest.mark.asyncio
async def test_post_interes_duplicado(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
) -> None:
    """Crear el mismo interés dos veces → 409 Conflict en el segundo."""
    user, _ = empresa_con_usuario

    payload = {"tipo": "unspsc_clase", "valor": "431601", "prioridad": 5}

    resp1 = await client.post(
        "/api/v1/intereses",
        json=payload,
        headers=_auth_headers(str(user.id)),
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        "/api/v1/intereses",
        json=payload,
        headers=_auth_headers(str(user.id)),
    )
    assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# Tests: DELETE /intereses/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_interes_ok(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    db_session: AsyncSession,
) -> None:
    """Crear interés y luego eliminarlo → 204, ya no existe en BD."""
    user, empresa = empresa_con_usuario

    # Crear interés directamente en BD
    interes = Interes(
        empresa_id=empresa.id,
        tipo=InteresTipo.keyword,
        valor="construcción",
        prioridad=5,
    )
    db_session.add(interes)
    await db_session.commit()
    await db_session.refresh(interes)

    resp = await client.delete(
        f"/api/v1/intereses/{interes.id}",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 204

    # Verificar eliminación en BD
    check = await db_session.execute(select(Interes).where(Interes.id == interes.id))
    assert check.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_interes_ajeno(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    segunda_empresa_con_usuario: tuple[Any, Any],
    db_session: AsyncSession,
) -> None:
    """Usuario B intenta eliminar interés de empresa A → 403 Forbidden."""
    user_a, empresa_a = empresa_con_usuario
    user_b, _ = segunda_empresa_con_usuario

    # Crear interés en empresa A
    interes_de_a = Interes(
        empresa_id=empresa_a.id,
        tipo=InteresTipo.keyword,
        valor="ingeniería civil",
        prioridad=8,
    )
    db_session.add(interes_de_a)
    await db_session.commit()
    await db_session.refresh(interes_de_a)

    # Usuario B intenta borrarlo
    resp = await client.delete(
        f"/api/v1/intereses/{interes_de_a.id}",
        headers=_auth_headers(str(user_b.id)),
    )
    assert resp.status_code == 403

    # El interés sigue existiendo
    check = await db_session.execute(select(Interes).where(Interes.id == interes_de_a.id))
    assert check.scalar_one_or_none() is not None
