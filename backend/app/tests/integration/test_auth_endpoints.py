"""Tests de integración para los endpoints de autenticación.

Requiere Postgres y Redis corriendo (docker compose up -d postgres redis).
Marcados como @pytest.mark.integration para correr selectivamente:
    pytest -m integration
"""

from collections.abc import Callable
from typing import Any

from httpx import AsyncClient
import pytest

pytestmark = pytest.mark.integration

# Alias de tipo para el factory de usuarios
UserFactory = Callable[..., Any]


@pytest.mark.asyncio
async def test_login_ok(client: AsyncClient, make_user: UserFactory) -> None:
    await make_user(email="login_ok@test.cl", password="TestPass123!")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_ok@test.cl", "password": "TestPass123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_credenciales_invalidas(
    client: AsyncClient, make_user: UserFactory
) -> None:
    await make_user(email="login_bad@test.cl", password="TestPass123!")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_bad@test.cl", "password": "WrongPass999!"},
    )
    assert resp.status_code == 401
    # Mensaje genérico — no distingue email vs password (regla de oro #4)
    assert "Credenciales inválidas" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_me_requiere_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_con_token_valido(client: AsyncClient, make_user: UserFactory) -> None:
    await make_user(email="me_test@test.cl", password="TestPass123!")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "me_test@test.cl", "password": "TestPass123!"},
    )
    access = login.json()["access_token"]

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "me_test@test.cl"


@pytest.mark.asyncio
async def test_flujo_completo_login_logout_refresh(
    client: AsyncClient, make_user: UserFactory
) -> None:
    await make_user(email="flujo@test.cl", password="TestPass123!")

    # Login
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "flujo@test.cl", "password": "TestPass123!"},
    )
    assert login.status_code == 200
    refresh_token = login.json()["refresh_token"]

    # Refresh → nuevo par de tokens
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    new_refresh = refresh_resp.json()["refresh_token"]

    # Logout con el nuevo refresh token
    logout_resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": new_refresh},
    )
    assert logout_resp.status_code == 204

    # Intentar usar el refresh revocado → 401
    retry = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert retry.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_viejo_invalido_tras_rotacion(
    client: AsyncClient, make_user: UserFactory
) -> None:
    """Tras rotar el token, el anterior queda revocado."""
    await make_user(email="rotate@test.cl", password="TestPass123!")

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "rotate@test.cl", "password": "TestPass123!"},
    )
    old_refresh = login.json()["refresh_token"]

    # Rotar
    await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})

    # El token viejo ya no sirve
    retry = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert retry.status_code == 401


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient, make_user: UserFactory) -> None:
    await make_user(
        email="changepw@test.cl",
        password="OldPass123!",
        must_change_password=True,
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "changepw@test.cl", "password": "OldPass123!"},
    )
    access = login.json()["access_token"]

    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OldPass123!", "new_password": "NewPass456!"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 204

    # Puede loguear con la nueva contraseña
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "changepw@test.cl", "password": "NewPass456!"},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_login(client: AsyncClient) -> None:
    """6 intentos seguidos desde la misma IP → 429 al sexto.

    Usa una IP ficticia via X-Forwarded-For para no contaminar otros tests.
    """
    # IP única para este test — evita que el rate-limit contamine otros tests
    rl_ip = "10.99.99.1"
    headers = {"X-Forwarded-For": rl_ip}

    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "noexiste@ratelimit.cl", "password": "Wrong!"},
            headers=headers,
        )
        assert resp.status_code == 401

    # El 6° debe ser 429
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "noexiste2@ratelimit.cl", "password": "Wrong!"},
        headers=headers,
    )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_forgot_password_respuesta_identica(client: AsyncClient) -> None:
    """Mismo status code si el email existe o no — anti-enumeración."""
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "noexiste@noexiste.cl"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_reset_password_token_invalido(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "token-falso", "new_password": "NewPass456!"},
    )
    assert resp.status_code == 400
