"""Caché Redis para respuestas frecuentes de la API.

Usa un connection pool persistente atado al event loop activo.
El pool se recrea automáticamente si el loop cambia (ej.: en tests con
pytest-asyncio que crea un loop nuevo por cada test).

Primitivas:
  get / set / delete  — operaciones crudas sobre strings.

Helper de alto nivel:
  cached()  — Read-Through con serialización Pydantic integrada.
              Reemplaza el patrón boilerplate get → compute → set.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import BaseModel
import redis.asyncio as aioredis

from app.config import settings

_pool: aioredis.ConnectionPool | None = None
_pool_loop: asyncio.AbstractEventLoop | None = None

T = TypeVar("T", bound=BaseModel)


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


async def set(key: str, value: str, ex: int) -> None:
    await _client().set(key, value, ex=ex)


async def delete(key: str) -> None:
    await _client().delete(key)


async def cached(
    key: str,
    miss: Callable[[], Awaitable[T]],
    model: type[T],
    *,
    ex: int,
) -> T:
    """Read-Through cache helper con serialización Pydantic.

    Busca `key` en Redis. Cache hit → deserializa y retorna.
    Cache miss → llama a `miss()`, serializa con model_dump_json y persiste
    con TTL `ex` segundos antes de retornar.

    Args:
        key:   Clave Redis. Usar prefijos descriptivos: "cat:regiones".
        miss:  Coroutine a ejecutar cuando no hay cache.
        model: Clase Pydantic del valor retornado (para model_validate_json).
        ex:    TTL en segundos.

    Example::

        response = await cache.cached(
            "cat:regiones",
            miss=lambda: _cargar_regiones_db(db),
            model=RegionesResponse,
            ex=86400,
        )
    """
    raw = await get(key)
    if raw is not None:
        return model.model_validate_json(raw)

    result = await miss()
    await set(key, result.model_dump_json(), ex=ex)
    return result
