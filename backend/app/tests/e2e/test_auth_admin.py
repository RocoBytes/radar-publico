"""Suite de tests de aceptación E2E — Autenticación (Epic 2) y Admin (Epic 1).

Cubre US-1.1 a US-1.4 y US-2.1 a US-2.4 según docs/spec.md.

Notas de implementación:
- Cada test crea su propio juego de datos (independencia total).
- Se usa real DB vía db_session del conftest raíz (patch_db_session activo).
- El cliente HTTP es AsyncClient con ASGITransport.
- Los tokens se generan sin round-trip HTTP con create_access_token().

BUGS CORREGIDOS:

BUG-1 (conftest e2e): e2e/conftest.py importaba `encrypt` de app.core.encryption;
  la función real es `encrypt_ticket`. Corregido en el conftest.

BUG-2 (US-2.1 — CORREGIDO): AccountSuspendedError y InvalidCredentialsError se
  capturaban juntos en auth.py. Separados en bloques except independientes para
  que cuentas suspendidas devuelvan "Cuenta no disponible. Contactá a soporte".

BUG-3 (US-1.2 — CORREGIDO): AdminService.cambiar_estado() y crear_cuenta() no
  cargaban selectinload(Empresa.ticket) → MissingGreenlet. Resuelto con reload
  query post-commit que incluye las relaciones anidadas.

BUGS PENDIENTES:

BUG-4 (US-1.2 / listar — CORREGIDO): La raíz no era MissingGreenlet sino
  una ValidationError de Pydantic: EmpresaResumen requiere tiene_ticket pero
  Empresa ORM no tenía ese atributo. Resuelto agregando @property tiene_ticket
  en el modelo Empresa para que from_attributes=True lo resuelva automáticamente.

BUG-5 (accion "activar" vs "reactivar" — CORREGIDO): CambiarEstadoRequest
  ahora acepta Literal["suspender", "reactivar", "activar"]. El servicio ya
  usaba else genérico, por lo que "activar" funciona sin cambios adicionales.

BUG-5 (accion "activar" vs "reactivar"): El spec US-1.2 menciona accion="activar"
  pero CambiarEstadoRequest acepta Literal["suspender", "reactivar"]. El test
  usa el valor correcto según el código ("reactivar"), no el del spec.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.encryption import encrypt_ticket
from app.core.security import create_access_token
from app.models.empresa import Empresa
from app.models.enums import TicketStatus, UserRole, UserStatus
from app.models.eventos_auditoria import AuditAction, EventoAuditoria
from app.models.password_reset import PasswordResetToken
from app.models.ticket import TicketApi
from app.models.usuario import Usuario

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Helpers de autenticación internos
# ---------------------------------------------------------------------------


def _auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    token = create_access_token(subject=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def _rut_from_seed(seed: str) -> str:
    """Genera un RUT en formato XX.XXX.XXX-K a partir de un seed string.

    Produce exactamente 8 dígitos (2+3+3) para satisfacer la regex
    ^DD.DDD.DDD-K (2+3+3 digits) del validador de RUT.
    """
    # Genera un número de 8 dígitos: range [10_000_000, 98_999_999]
    n = (int(seed, 16) % 89_000_000) + 10_000_000
    s = str(n)  # exactamente 8 dígitos
    return f"{s[:2]}.{s[2:5]}.{s[5:8]}-K"


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def admin_user(make_user: Callable[..., Any]) -> Usuario:
    """Crea un usuario con rol admin activo."""
    return await make_user(
        email=f"admin_{uuid.uuid4().hex[:8]}@radar.cl",
        password="AdminPass123!",
        rol=UserRole.admin,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=False,
    )


@pytest_asyncio.fixture
async def proveedor_user(make_user: Callable[..., Any]) -> Usuario:
    """Crea un proveedor activo con empresa."""
    seed = uuid.uuid4().hex[:8]
    return await make_user(
        email=f"prov_{seed}@empresa.cl",
        password="ProvPass123!",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        must_change_password=False,
        with_empresa=True,
        rut=_rut_from_seed(seed),
        razon_social="E2E SpA",
    )


# ---------------------------------------------------------------------------
# US-2.1 — Login
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_login_cuenta_suspendida_retorna_mensaje_spec(
    client: AsyncClient,
    make_user: Callable[..., Any],
) -> None:
    """US-2.1: cuenta suspendida con credenciales válidas → mensaje del spec."""
    email = f"susp_{uuid.uuid4().hex[:8]}@test.cl"
    password = "TestSusp123!"
    await make_user(
        email=email,
        password=password,
        rol=UserRole.proveedor,
        status=UserStatus.suspended,
        with_empresa=False,
    )

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )

    assert resp.status_code == 401
    # El spec dice este mensaje; el código real devuelve "Credenciales inválidas"
    assert "Cuenta no disponible" in resp.json()["detail"]


@pytest.mark.e2e
async def test_login_incrementa_failed_attempts(
    client: AsyncClient,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """US-2.1: contraseña incorrecta → failed_login_attempts se incrementa en BD."""
    email = f"fail_{uuid.uuid4().hex[:8]}@test.cl"
    user = await make_user(
        email=email,
        password="CorrectPass123!",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=False,
    )
    user_id = user.id

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword123!"},
    )
    assert resp.status_code == 401

    # Refetch desde la BD para obtener el estado actualizado
    db_session.expire_all()  # expire_all es síncrono en SQLAlchemy
    result = await db_session.execute(select(Usuario).where(Usuario.id == user_id))
    fresh = result.scalar_one()
    assert fresh.failed_login_attempts >= 1


@pytest.mark.e2e
async def test_login_cuenta_bloqueada_no_cuenta_intentos(
    client: AsyncClient,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """US-2.1: cuenta ya bloqueada (locked_until en futuro) → 401 sin incrementar contador."""
    from sqlalchemy import update

    email = f"lock_{uuid.uuid4().hex[:8]}@test.cl"
    user = await make_user(
        email=email,
        password="TestLock123!",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=False,
    )
    user_id = user.id

    # Setear locked_until directamente en BD con intentos = 3
    await db_session.execute(
        update(Usuario)
        .where(Usuario.id == user_id)
        .values(
            locked_until=datetime.now(UTC) + timedelta(minutes=30),
            failed_login_attempts=3,
        )
    )
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPass123!"},
    )
    # AccountLockedError → 401
    assert resp.status_code == 401

    # failed_login_attempts NO debe haber aumentado
    db_session.expire_all()  # expire_all es síncrono en SQLAlchemy
    result = await db_session.execute(select(Usuario).where(Usuario.id == user_id))
    fresh = result.scalar_one()
    assert fresh.failed_login_attempts == 3, (
        f"Se esperaban 3 intentos fallidos, got {fresh.failed_login_attempts}. "
        "La cuenta bloqueada no debería incrementar el contador."
    )


@pytest.mark.e2e
async def test_login_emite_evento_auditoria(
    client: AsyncClient,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """US-2.1: login exitoso → EventoAuditoria con accion=auth.login.success."""
    email = f"audit_{uuid.uuid4().hex[:8]}@test.cl"
    password = "AuditPass123!"
    user = await make_user(
        email=email,
        password=password,
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=False,
    )
    user_id = user.id

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200

    # Verificar evento en BD
    result = await db_session.execute(
        select(EventoAuditoria).where(
            EventoAuditoria.usuario_id == user_id,
            EventoAuditoria.accion == AuditAction.LOGIN_OK,
        )
    )
    evento = result.scalars().first()
    assert (
        evento is not None
    ), f"No se encontró evento '{AuditAction.LOGIN_OK}' para usuario {user_id}"


# ---------------------------------------------------------------------------
# US-2.3 — Password reset
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_reset_password_flujo_completo(
    client: AsyncClient,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """US-2.3: forgot-password → token en BD → reset → nueva contraseña funciona."""
    from app.core.security import generate_reset_token

    email = f"reset_{uuid.uuid4().hex[:8]}@test.cl"
    old_password = "OldPass123!"
    new_password = "NewPassword123!"

    user = await make_user(
        email=email,
        password=old_password,
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=False,
    )
    user_id = user.id

    # 1) Solicitar reset (siempre 204 — anti-enumeración)
    resp_forgot = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": email},
    )
    assert resp_forgot.status_code == 204

    # 2) Verificar token creado en BD
    result = await db_session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.usuario_id == user_id,
            PasswordResetToken.usado_at.is_(None),
        )
    )
    prt = result.scalars().first()
    assert prt is not None, "No se creó PasswordResetToken en BD"
    assert prt.expires_at > datetime.now(UTC), "El token ya expiró al crearse"

    # 3) El plaintext no está en BD — creamos un token conocido y lo asignamos
    plain_token, token_hash = generate_reset_token()
    prt.token_hash = token_hash
    await db_session.commit()

    # 4) Usar el token para resetear
    resp_reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": plain_token, "new_password": new_password},
    )
    assert resp_reset.status_code == 204

    # 5) La nueva contraseña debe funcionar
    resp_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": new_password},
    )
    assert resp_login.status_code == 200

    # 6) La contraseña vieja ya NO debe funcionar
    resp_old = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": old_password},
    )
    assert resp_old.status_code == 401


@pytest.mark.e2e
async def test_reset_password_token_expiro(
    client: AsyncClient,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """US-2.3: token expirado → 400."""
    from app.core.security import generate_reset_token

    user = await make_user(
        email=f"exp_{uuid.uuid4().hex[:8]}@test.cl",
        password="TestExp123!",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=False,
    )

    plain_token, token_hash = generate_reset_token()

    # Crear token expirado en BD
    prt = PasswordResetToken(
        usuario_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db_session.add(prt)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": plain_token, "new_password": "NewValid123!"},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "inválido" in detail or "expirado" in detail or "invalido" in detail


@pytest.mark.e2e
async def test_reset_password_token_un_solo_uso(
    client: AsyncClient,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """US-2.3: token válido usado → 204. Reutilizar el mismo token → 400."""
    from app.core.security import generate_reset_token

    user = await make_user(
        email=f"singleuse_{uuid.uuid4().hex[:8]}@test.cl",
        password="TestSingle123!",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=False,
    )

    plain_token, token_hash = generate_reset_token()

    prt = PasswordResetToken(
        usuario_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    db_session.add(prt)
    await db_session.commit()

    # Primer uso → debe funcionar
    resp_first = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": plain_token, "new_password": "FirstNewPass123!"},
    )
    assert resp_first.status_code == 204

    # Segundo uso mismo token → debe rechazarse
    resp_second = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": plain_token, "new_password": "SecondNewPass123!"},
    )
    assert resp_second.status_code == 400


# ---------------------------------------------------------------------------
# US-2.4 — Cambiar contraseña (política de seguridad)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_change_password_politica_muy_corta(
    client: AsyncClient,
    make_user: Callable[..., Any],
) -> None:
    """US-2.4: nueva contraseña < 10 caracteres → 422."""
    user = await make_user(
        email=f"chpw_{uuid.uuid4().hex[:8]}@test.cl",
        password="ValidPass123!",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=False,
    )
    headers = _auth_headers(user.id)

    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "ValidPass123!", "new_password": "Short1A"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.e2e
async def test_change_password_politica_sin_mayuscula(
    client: AsyncClient,
    make_user: Callable[..., Any],
) -> None:
    """US-2.4: nueva contraseña sin mayúscula → 422."""
    user = await make_user(
        email=f"chpw2_{uuid.uuid4().hex[:8]}@test.cl",
        password="ValidPass123!",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=False,
    )
    headers = _auth_headers(user.id)

    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "ValidPass123!", "new_password": "alllowercase123"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.e2e
async def test_change_password_politica_sin_numero(
    client: AsyncClient,
    make_user: Callable[..., Any],
) -> None:
    """US-2.4: nueva contraseña sin número → 422."""
    user = await make_user(
        email=f"chpw3_{uuid.uuid4().hex[:8]}@test.cl",
        password="ValidPass123!",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=False,
    )
    headers = _auth_headers(user.id)

    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "ValidPass123!", "new_password": "NoNumbersHere!"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.e2e
async def test_change_password_invalida_otras_sesiones(
    client: AsyncClient,
    make_user: Callable[..., Any],
) -> None:
    """US-2.4: cambiar contraseña revoca refresh tokens de otras sesiones."""
    email = f"mulsess_{uuid.uuid4().hex[:8]}@test.cl"
    password = "MultiSess123!"
    new_password = "NewMultiSess123!"

    await make_user(
        email=email,
        password=password,
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=False,
    )

    # Sesión 1: login → obtener refresh token 1
    resp1 = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp1.status_code == 200
    refresh_token_1 = resp1.json()["refresh_token"]

    # Sesión 2: segundo login → obtener acceso + refresh 2
    resp2 = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp2.status_code == 200
    refresh_token_2 = resp2.json()["refresh_token"]
    resp2.json()["access_token"]

    # Verificar que refresh_token_2 funciona antes del cambio
    resp_pre = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_2},
    )
    assert resp_pre.status_code == 200
    # El refresh rotó; usamos el nuevo
    resp_pre.json()["refresh_token"]
    new_access_2 = resp_pre.json()["access_token"]

    # Cambiar contraseña desde sesión 2 (sin cookie de refresh → current_refresh_hash="")
    resp_change = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": password, "new_password": new_password},
        headers={"Authorization": f"Bearer {new_access_2}"},
    )
    assert resp_change.status_code == 204

    # refresh_token_1 (sesión anterior) debe estar revocado
    resp_old_refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_1},
    )
    assert resp_old_refresh.status_code == 401, (
        "El refresh token de la sesión anterior debería haberse revocado "
        "al cambiar la contraseña"
    )


# ---------------------------------------------------------------------------
# US-1.1 — Crear cuenta (admin)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_admin_crear_cuenta_ok(
    client: AsyncClient,
    admin_user: Usuario,
) -> None:
    """US-1.1: admin crea cuenta → 201, temp_password presente, must_change_password=True."""
    headers = _auth_headers(admin_user.id)
    seed = uuid.uuid4().hex[:8]

    resp = await client.post(
        "/api/admin/cuentas",
        json={
            "email": f"nuevo_{seed}@empresa.cl",
            "rut": _rut_from_seed(seed),
            "razon_social": "Nueva Empresa SpA",
        },
        headers=headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert "temp_password" in data, f"Falta temp_password en respuesta: {list(data.keys())}"
    assert data["temp_password"], "temp_password no puede estar vacía"
    assert data["must_change_password"] is True, "must_change_password debe ser True"


@pytest.mark.e2e
async def test_admin_crear_cuenta_email_duplicado(
    client: AsyncClient,
    admin_user: Usuario,
    make_user: Callable[..., Any],
) -> None:
    """US-1.1: crear cuenta con email ya registrado → 409."""
    seed = uuid.uuid4().hex[:8]
    existing_email = f"dup_{seed}@empresa.cl"
    existing_rut = _rut_from_seed(seed)

    await make_user(
        email=existing_email,
        password="ExistPass123!",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=True,
        rut=existing_rut,
        razon_social="Empresa Existente SpA",
    )

    headers = _auth_headers(admin_user.id)
    seed2 = uuid.uuid4().hex[:8]
    resp = await client.post(
        "/api/admin/cuentas",
        json={
            "email": existing_email,
            "rut": _rut_from_seed(seed2),
            "razon_social": "Intento Duplicado SpA",
        },
        headers=headers,
    )

    assert resp.status_code == 409


@pytest.mark.e2e
async def test_admin_proveedor_no_puede_crear_cuenta(
    client: AsyncClient,
    proveedor_user: Usuario,
) -> None:
    """US-1.1: proveedor intenta crear cuenta → 403."""
    headers = _auth_headers(proveedor_user.id)
    seed = uuid.uuid4().hex[:8]

    resp = await client.post(
        "/api/admin/cuentas",
        json={
            "email": f"nuevo_{seed}@empresa.cl",
            "rut": _rut_from_seed(seed),
            "razon_social": "Intento No Autorizado SpA",
        },
        headers=headers,
    )

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# US-1.2 — Suspender / activar cuenta
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_admin_suspender_cuenta(
    client: AsyncClient,
    admin_user: Usuario,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """US-1.2: admin suspende cuenta → status=suspended, usuario no puede loguear."""
    email = f"susp_target_{uuid.uuid4().hex[:8]}@test.cl"
    password = "TargetPass123!"
    target = await make_user(
        email=email,
        password=password,
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=False,
    )
    admin_headers = _auth_headers(admin_user.id)

    resp = await client.patch(
        f"/api/admin/cuentas/{target.id}/estado",
        json={"accion": "suspender"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "suspended"

    # El usuario ya no puede loguearse
    resp_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp_login.status_code == 401


@pytest.mark.e2e
async def test_admin_activar_cuenta_suspendida(
    client: AsyncClient,
    admin_user: Usuario,
    make_user: Callable[..., Any],
) -> None:
    """US-1.2: admin suspende y reactiva → usuario puede loguear de nuevo.

    Nota: el endpoint usa accion='reactivar' (BUG-5: spec dice 'activar').
    """
    email = f"react_{uuid.uuid4().hex[:8]}@test.cl"
    password = "ReactPass123!"
    target = await make_user(
        email=email,
        password=password,
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=False,
    )
    admin_headers = _auth_headers(admin_user.id)

    # Suspender
    await client.patch(
        f"/api/admin/cuentas/{target.id}/estado",
        json={"accion": "suspender"},
        headers=admin_headers,
    )

    # Reactivar — el schema usa "reactivar", no "activar"
    resp = await client.patch(
        f"/api/admin/cuentas/{target.id}/estado",
        json={"accion": "reactivar"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

    # Ahora el usuario puede loguear
    resp_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp_login.status_code == 200


@pytest.mark.e2e
async def test_admin_activar_con_valor_spec(
    client: AsyncClient,
    admin_user: Usuario,
    make_user: Callable[..., Any],
) -> None:
    """US-1.2 / BUG-5: accion='activar' (valor del spec) debe funcionar igual que 'reactivar'."""
    email = f"activar_spec_{uuid.uuid4().hex[:8]}@test.cl"
    password = "ActivarSpec123!"
    target = await make_user(
        email=email,
        password=password,
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=False,
    )
    admin_headers = _auth_headers(admin_user.id)

    # Suspender primero
    await client.patch(
        f"/api/admin/cuentas/{target.id}/estado",
        json={"accion": "suspender"},
        headers=admin_headers,
    )

    # Reactivar usando el valor del spec ("activar")
    resp = await client.patch(
        f"/api/admin/cuentas/{target.id}/estado",
        json={"accion": "activar"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

    # El usuario puede loguear de nuevo
    resp_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp_login.status_code == 200


# ---------------------------------------------------------------------------
# US-1.3 — Cargar ticket (cifrado AES-256)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_admin_cargar_ticket_cifra_aes256(
    client: AsyncClient,
    admin_user: Usuario,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """US-1.3: admin carga ticket → cifrado en BD, últimos 4 chars en respuesta."""
    ticket_plain = "ABCD-1234-EFGH-5678"
    seed = uuid.uuid4().hex[:8]
    target = await make_user(
        email=f"tick_{seed}@empresa.cl",
        password="TickPass123!",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=True,
        rut=_rut_from_seed(seed),
        razon_social="Ticket SpA",
    )
    admin_headers = _auth_headers(admin_user.id)

    resp = await client.post(
        f"/api/admin/cuentas/{target.id}/ticket",
        json={"ticket": ticket_plain},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    # FastAPI usa by_alias=True → la clave en JSON es "ticket_ultimos_4" (el alias)
    assert (
        data.get("ticket_ultimos_4") == ticket_plain[-4:]
    ), f"Se esperaba ticket_ultimos_4='{ticket_plain[-4:]}', got {data}"
    # El ticket completo NO debe estar en la respuesta
    assert ticket_plain not in str(data), "El ticket en claro nunca debe estar en la respuesta"

    # Verificar en BD que ticket_cifrado != ticket_plain
    empresa_result = await db_session.execute(
        select(Empresa).where(Empresa.usuario_id == target.id)
    )
    empresa = empresa_result.scalar_one()

    ticket_result = await db_session.execute(
        select(TicketApi).where(TicketApi.empresa_id == empresa.id)
    )
    ticket_db = ticket_result.scalar_one()

    assert (
        ticket_db.ticket_cifrado != ticket_plain
    ), "El ticket se almacenó en texto claro — debe estar cifrado"
    assert len(ticket_db.ticket_cifrado) > len(
        ticket_plain
    ), "El valor cifrado debería ser más largo que el plaintext (nonce + ciphertext)"

    # Limpiar el ticket antes del teardown para evitar FK violation
    # (tickets_api.cargado_por_admin_id → admin_user, con ON DELETE SET NULL
    # en el schema pero la sesión compartida puede causar conflicto de autoflush)
    await db_session.delete(ticket_db)
    await db_session.commit()


@pytest.mark.e2e
async def test_admin_ticket_nunca_expuesto_completo(
    client: AsyncClient,
    admin_user: Usuario,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """US-1.3: GET diagnóstico → respuesta NO contiene el ticket completo ni cifrado."""
    ticket_plain = "SECRET-TICKET-ABCD-9999"
    seed = uuid.uuid4().hex[:8]
    target = await make_user(
        email=f"diag_{seed}@empresa.cl",
        password="DiagPass123!",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=True,
        rut=_rut_from_seed(seed),
        razon_social="Diagnostico SpA",
    )

    # Crear ticket en BD directamente SIN cargado_por_admin_id
    # (evita FK violation en teardown cuando se borra el admin_user)
    empresa_result = await db_session.execute(
        select(Empresa).where(Empresa.usuario_id == target.id)
    )
    empresa = empresa_result.scalar_one()

    ticket_cifrado_val = encrypt_ticket(ticket_plain)
    ticket = TicketApi(
        empresa_id=empresa.id,
        ticket_cifrado=ticket_cifrado_val,
        ticket_ultimos_4=ticket_plain[-4:],
        status=TicketStatus.active,
        # cargado_por_admin_id intencialmente NULL para evitar FK en teardown
    )
    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)
    ticket_id = ticket.id

    admin_headers = _auth_headers(admin_user.id)
    resp = await client.get(
        f"/api/admin/cuentas/{target.id}/ticket/diagnostico",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    resp_text = resp.text

    # El ticket en claro nunca debe aparecer en ninguna respuesta (regla #2)
    assert (
        ticket_plain not in resp_text
    ), "El ticket en claro fue expuesto en la respuesta del diagnóstico"
    # El valor cifrado base64 tampoco debe aparecer
    assert (
        ticket_cifrado_val not in resp_text
    ), "El ticket cifrado fue expuesto en la respuesta del diagnóstico"

    # Limpiar ticket antes del teardown
    ticket_to_del = await db_session.get(TicketApi, ticket_id)
    if ticket_to_del:
        await db_session.delete(ticket_to_del)
        await db_session.commit()


# ---------------------------------------------------------------------------
# US-1.4 — Impersonación + auditoría
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_admin_impersonar_registra_auditoria(
    client: AsyncClient,
    admin_user: Usuario,
    make_user: Callable[..., Any],
    db_session: AsyncSession,
) -> None:
    """US-1.4: impersonar → EventoAuditoria con admin como actor y target en recurso_id."""
    target = await make_user(
        email=f"imp_{uuid.uuid4().hex[:8]}@empresa.cl",
        password="ImpPass123!",
        rol=UserRole.proveedor,
        status=UserStatus.active,
        with_empresa=False,
    )
    admin_headers = _auth_headers(admin_user.id)

    resp = await client.post(
        f"/api/admin/cuentas/{target.id}/impersonar",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()

    # Verificar registro de auditoría
    result = await db_session.execute(
        select(EventoAuditoria).where(
            EventoAuditoria.usuario_id == admin_user.id,
            EventoAuditoria.accion == "admin.cuenta.impersonada",
        )
    )
    evento = result.scalars().first()
    assert evento is not None, "No se encontró evento de auditoría 'admin.cuenta.impersonada'"
    assert evento.recurso_id == str(
        target.id
    ), f"recurso_id debería ser {target.id}, got {evento.recurso_id}"


# ---------------------------------------------------------------------------
# Security negative paths
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_proveedor_no_accede_admin_endpoints(
    client: AsyncClient,
    proveedor_user: Usuario,
) -> None:
    """Seguridad: proveedor con token válido → 403 en GET /api/admin/cuentas."""
    headers = _auth_headers(proveedor_user.id)

    resp = await client.get("/api/admin/cuentas", headers=headers)
    assert resp.status_code == 403


@pytest.mark.e2e
async def test_sin_token_todos_los_endpoints_protegidos(
    client: AsyncClient,
) -> None:
    """Seguridad: sin Bearer token → 401 en todos los endpoints protegidos."""
    endpoints = [
        ("GET", "/api/v1/licitaciones"),
        ("GET", "/api/v1/pipeline"),
        ("GET", "/api/v1/empresa/me"),
        ("GET", "/api/v1/radares"),
        ("GET", "/api/v1/notificaciones/resumen"),
    ]

    for method, path in endpoints:
        resp = await client.request(method, path)
        assert (
            resp.status_code == 401
        ), f"Se esperaba 401 en {method} {path} sin token, got {resp.status_code}"


@pytest.mark.e2e
async def test_multi_tenancy_admin_ve_todas_cuentas_proveedor_no(
    client: AsyncClient,
    admin_user: Usuario,
    proveedor_user: Usuario,
) -> None:
    """US-1.1 / multi-tenancy: admin puede listar cuentas; proveedor recibe 403."""
    admin_headers = _auth_headers(admin_user.id)
    prov_headers = _auth_headers(proveedor_user.id)

    # Admin puede acceder
    resp_admin = await client.get("/api/admin/cuentas", headers=admin_headers)
    assert resp_admin.status_code == 200
    data = resp_admin.json()
    assert "items" in data
    assert "total" in data

    # Proveedor no puede
    resp_prov = await client.get("/api/admin/cuentas", headers=prov_headers)
    assert resp_prov.status_code == 403
