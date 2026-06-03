"""Tests unitarios para los endpoints de radares.

Cubre:
  GET    /api/v1/radares
  POST   /api/v1/radares
  GET    /api/v1/radares/{id}
  PATCH  /api/v1/radares/{id}
  DELETE /api/v1/radares/{id}

Usa BD de test real con AsyncClient + ASGITransport.
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
from app.models.radar import Radar

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession


def _auth_headers(user_id: str) -> dict[str, str]:
    token = create_access_token(subject=user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(autouse=True)
async def limpiar_radares(db_session: AsyncSession) -> None:
    await db_session.execute(delete(Radar))
    await db_session.commit()


@pytest_asyncio.fixture
async def empresa_con_usuario(
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> tuple[Any, Empresa]:
    user: Any = await make_user(
        email="radares_test@example.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        razon_social="Radar Test SpA",
    )
    result = await db_session.execute(select(Empresa).where(Empresa.usuario_id == user.id))
    empresa: Empresa = result.scalar_one()
    return user, empresa


@pytest_asyncio.fixture
async def segunda_empresa_con_usuario(
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> tuple[Any, Empresa]:
    user: Any = await make_user(
        email="radares_otra@example.cl",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        razon_social="Otra Empresa SpA",
    )
    result = await db_session.execute(select(Empresa).where(Empresa.usuario_id == user.id))
    empresa: Empresa = result.scalar_one()
    return user, empresa


# ---------------------------------------------------------------------------
# GET /radares — listado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_radares_vacio(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
) -> None:
    user, _ = empresa_con_usuario
    resp = await client.get("/api/v1/radares", headers=_auth_headers(str(user.id)))
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_listar_radares_sin_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/radares")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /radares — creación
# ---------------------------------------------------------------------------

_PAYLOAD_BASICO = {
    "nombre": "Radar limpieza RM",
    "filtros": {"q": "limpieza", "unspsc_codigo": "73"},
    "notif_canal": "email",
    "notif_frecuencia": "instantaneo",
    "notif_score_minimo": 60,
}


@pytest.mark.asyncio
async def test_crear_radar_ok(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
) -> None:
    user, _ = empresa_con_usuario
    resp = await client.post(
        "/api/v1/radares",
        json=_PAYLOAD_BASICO,
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["nombre"] == "Radar limpieza RM"
    assert data["filtros"]["q"] == "limpieza"
    assert data["filtros"]["unspsc_codigo"] == "73"
    assert data["activo"] is True
    assert data["notif_score_minimo"] == 60
    assert "id" in data
    assert "created_at" in data
    assert "ultima_ejecucion_at" in data


@pytest.mark.asyncio
async def test_crear_radar_sin_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/radares", json=_PAYLOAD_BASICO)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_crear_radar_nombre_vacio_retorna_422(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
) -> None:
    user, _ = empresa_con_usuario
    resp = await client.post(
        "/api/v1/radares",
        json={**_PAYLOAD_BASICO, "nombre": ""},
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_crear_radar_limita_a_20(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    db_session: AsyncSession,
) -> None:
    """Empresa con 20 radares → siguiente POST retorna 400 (US-5.3: máx 20)."""
    user, empresa = empresa_con_usuario

    radares = [
        Radar(
            empresa_id=empresa.id,
            nombre=f"Radar {i}",
            filtros={},
        )
        for i in range(20)
    ]
    db_session.add_all(radares)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/radares",
        json=_PAYLOAD_BASICO,
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /radares/{id} — detalle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_obtener_radar_ok(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    db_session: AsyncSession,
) -> None:
    user, empresa = empresa_con_usuario

    radar = Radar(
        empresa_id=empresa.id,
        nombre="Mi radar",
        filtros={"q": "aseo"},
    )
    db_session.add(radar)
    await db_session.commit()
    await db_session.refresh(radar)

    resp = await client.get(
        f"/api/v1/radares/{radar.id}",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(radar.id)


@pytest.mark.asyncio
async def test_obtener_radar_no_existente_retorna_404(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
) -> None:
    import uuid

    user, _ = empresa_con_usuario
    resp = await client.get(
        f"/api/v1/radares/{uuid.uuid4()}",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_obtener_radar_ajeno_retorna_403(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    segunda_empresa_con_usuario: tuple[Any, Any],
    db_session: AsyncSession,
) -> None:
    user_a, empresa_a = empresa_con_usuario
    user_b, _ = segunda_empresa_con_usuario

    radar_de_a = Radar(empresa_id=empresa_a.id, nombre="Privado", filtros={})
    db_session.add(radar_de_a)
    await db_session.commit()
    await db_session.refresh(radar_de_a)

    resp = await client.get(
        f"/api/v1/radares/{radar_de_a.id}",
        headers=_auth_headers(str(user_b.id)),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /radares/{id} — actualización parcial
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_radar_nombre(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    db_session: AsyncSession,
) -> None:
    user, empresa = empresa_con_usuario

    radar = Radar(empresa_id=empresa.id, nombre="Nombre viejo", filtros={"q": "x"})
    db_session.add(radar)
    await db_session.commit()
    await db_session.refresh(radar)

    resp = await client.patch(
        f"/api/v1/radares/{radar.id}",
        json={"nombre": "Nombre nuevo"},
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["nombre"] == "Nombre nuevo"
    assert data["filtros"]["q"] == "x"  # filtros no cambiaron


@pytest.mark.asyncio
async def test_patch_radar_desactivar(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    db_session: AsyncSession,
) -> None:
    user, empresa = empresa_con_usuario

    radar = Radar(empresa_id=empresa.id, nombre="Activo", filtros={})
    db_session.add(radar)
    await db_session.commit()
    await db_session.refresh(radar)

    resp = await client.patch(
        f"/api/v1/radares/{radar.id}",
        json={"activo": False},
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    assert resp.json()["activo"] is False


@pytest.mark.asyncio
async def test_patch_radar_actualiza_filtros(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    db_session: AsyncSession,
) -> None:
    user, empresa = empresa_con_usuario

    radar = Radar(empresa_id=empresa.id, nombre="Test", filtros={"q": "viejo"})
    db_session.add(radar)
    await db_session.commit()
    await db_session.refresh(radar)

    resp = await client.patch(
        f"/api/v1/radares/{radar.id}",
        json={"filtros": {"q": "nuevo", "unspsc_codigo": "80"}},
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filtros"]["q"] == "nuevo"
    assert data["filtros"]["unspsc_codigo"] == "80"


# ---------------------------------------------------------------------------
# DELETE /radares/{id} — eliminación
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_radar_ok(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    db_session: AsyncSession,
) -> None:
    user, empresa = empresa_con_usuario

    radar = Radar(empresa_id=empresa.id, nombre="A eliminar", filtros={})
    db_session.add(radar)
    await db_session.commit()
    await db_session.refresh(radar)

    resp = await client.delete(
        f"/api/v1/radares/{radar.id}",
        headers=_auth_headers(str(user.id)),
    )
    assert resp.status_code == 204

    check = await db_session.execute(select(Radar).where(Radar.id == radar.id))
    assert check.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_radar_ajeno_retorna_403(
    client: AsyncClient,
    empresa_con_usuario: tuple[Any, Any],
    segunda_empresa_con_usuario: tuple[Any, Any],
    db_session: AsyncSession,
) -> None:
    user_a, empresa_a = empresa_con_usuario
    user_b, _ = segunda_empresa_con_usuario

    radar_de_a = Radar(empresa_id=empresa_a.id, nombre="De A", filtros={})
    db_session.add(radar_de_a)
    await db_session.commit()
    await db_session.refresh(radar_de_a)

    resp = await client.delete(
        f"/api/v1/radares/{radar_de_a.id}",
        headers=_auth_headers(str(user_b.id)),
    )
    assert resp.status_code == 403

    # El radar sigue existiendo
    check = await db_session.execute(select(Radar).where(Radar.id == radar_de_a.id))
    assert check.scalar_one_or_none() is not None
