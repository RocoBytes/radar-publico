"""Configuración global de pytest.

Fixtures compartidas entre tests unitarios e integración.
"""

from collections.abc import AsyncGenerator, Callable, Generator
from typing import Any
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.security import hash_password
from app.db import session as _db_session_module
from app.main import app
from app.models.empresa import Empresa
from app.models.enums import UserRole, UserStatus
from app.models.usuario import Usuario

# Engine de test con NullPool — sin conexiones compartidas entre event loops.
# Esto evita el error "Future attached to a different loop" de asyncpg
# cuando pytest-asyncio crea un loop nuevo por cada test.
_test_engine = create_async_engine(
    settings.database_url,
    echo=False,
    poolclass=NullPool,
)
_TestSessionLocal = async_sessionmaker(
    _test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Usa asyncio como backend para tests async."""
    return "asyncio"


@pytest.fixture(autouse=True)
def encryption_key_valida(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Garantiza que ENCRYPTION_KEY tiene 32 bytes en tests de cifrado."""
    if "test_encryption" not in request.node.nodeid:
        yield
        return
    with patch("app.core.encryption.settings") as mock_settings:
        mock_settings.encryption_key = "A" * 32
        yield


@pytest_asyncio.fixture(autouse=True)
async def reset_redis_rate_limits() -> AsyncGenerator[None, None]:
    """Limpia las keys de rate-limit de Redis antes de cada test.

    Evita que el test_rate_limit_login contamine los tests siguientes
    cuando todos usan la misma IP virtual del ASGI transport.
    """
    import redis.asyncio as aioredis

    client = aioredis.from_url(  # type: ignore[no-untyped-call]
        settings.redis_url, decode_responses=True
    )
    # Borrar todas las keys de rate-limit de auth
    async for key in client.scan_iter("login:*"):
        await client.delete(key)
    async for key in client.scan_iter("forgot:*"):
        await client.delete(key)
    await client.aclose()
    yield


@pytest_asyncio.fixture(autouse=True)
async def patch_db_session() -> AsyncGenerator[None, None]:
    """Parcha AsyncSessionLocal de la app para usar NullPool en tests.

    Esto garantiza que tanto make_user como la app ASGI usen el mismo
    engine sin pool compartido, evitando el error 'Future attached to
    a different loop' de asyncpg con pytest-asyncio.
    """
    original = _db_session_module.AsyncSessionLocal
    _db_session_module.AsyncSessionLocal = _TestSessionLocal
    yield
    _db_session_module.AsyncSessionLocal = original


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Session de BD para uso directo en fixtures."""
    async with _TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP contra la app ASGI real."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest_asyncio.fixture
async def make_user() -> AsyncGenerator[Callable[..., Any], None]:
    """Factory que crea usuarios con commit real. Limpia al finalizar."""
    emails_creados: list[str] = []

    async def _factory(
        email: str = "test@example.cl",
        password: str = "TestPassword123!",
        rol: UserRole = UserRole.proveedor,
        status: UserStatus = UserStatus.active,
        must_change_password: bool = False,
        with_empresa: bool = True,
        rut: str | None = None,
        razon_social: str = "Test Empresa SpA",
    ) -> Usuario:
        rut_final = rut or f"76.{abs(hash(email)) % 999_999:06d}-K"
        async with _TestSessionLocal() as session:
            # Idempotente: limpia usuario previo con este email
            existing_result = await session.execute(
                select(Usuario).where(Usuario.email == email)
            )
            existing = existing_result.scalar_one_or_none()
            if existing is not None:
                await session.delete(existing)
                await session.commit()

            user = Usuario(
                email=email,
                password_hash=hash_password(password),
                rol=rol,
                status=status,
                must_change_password=must_change_password,
            )
            session.add(user)
            await session.flush()

            if with_empresa and rol == UserRole.proveedor:
                empresa = Empresa(
                    usuario_id=user.id,
                    rut=rut_final,
                    razon_social=razon_social,
                )
                session.add(empresa)

            await session.commit()
            await session.refresh(user)

        emails_creados.append(email)
        return user

    yield _factory

    # Teardown
    async with _TestSessionLocal() as session:
        for email in emails_creados:
            result = await session.execute(
                select(Usuario).where(Usuario.email == email)
            )
            user = result.scalar_one_or_none()
            if user is not None:
                await session.delete(user)
        await session.commit()
