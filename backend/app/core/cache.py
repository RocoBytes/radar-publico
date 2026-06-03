"""Caché Redis para respuestas frecuentes de la API.

Usa un connection pool persistente atado al event loop activo.
El pool se recrea automáticamente si el loop cambia (ej.: en tests con
pytest-asyncio que crea un loop nuevo por cada test).
El TTL corto (30 s) elimina la necesidad de invalidación explícita en la
mayoría de los casos. Cuando se necesita invalidación inmediata (ej.:
cambio de onboarding_completado) usar `delete()`.
"""

from __future__ import annotations

import asyncio

import redis.asyncio as aioredis

from app.config import settings

_pool: aioredis.ConnectionPool | None = None
_pool_loop: asyncio.AbstractEventLoop | None = None


def _get_pool() -> aioredis.ConnectionPool:
    global _pool, _pool_loop
    try:
        current_loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _pool is None or _pool_loop is not current_loop:
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=10,
        )
        _pool_loop = current_loop
    return _pool


def _client() -> aioredis.Redis:
    return aioredis.Redis(connection_pool=_get_pool())


async def get(key: str) -> str | None:
    return await _client().get(key)  # type: ignore[no-any-return]


async def set(key: str, value: str, ex: int = 30) -> None:
    await _client().set(key, value, ex=ex)


async def delete(key: str) -> None:
    await _client().delete(key)
