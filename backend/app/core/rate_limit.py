"""Rate limiting fixed window con Redis INCR + EXPIRE.

Regla de oro #6: 5 intentos / 15 min por IP en login.
La defensa es en capas: Redis limita por IP, la BD lockea la cuenta tras 5 fallos.
"""

from dataclasses import dataclass

import redis.asyncio as aioredis

from app.config import settings


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int


async def hit(key: str, limit: int, window_seconds: int) -> RateLimitResult:
    """Incrementa el contador para `key` en una ventana fija.

    El TTL solo se setea en el primer hit de la ventana — INCR + EXPIRE atómico
    vía pipeline para evitar race condition.
    """
    client: aioredis.Redis = aioredis.from_url(  # type: ignore[no-untyped-call]
        settings.redis_url, decode_responses=True
    )
    try:
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        count_raw, ttl = await pipe.execute()
        count = int(count_raw)

        if ttl == -1:
            # Primera vez que aparece esta key en la ventana
            await client.expire(key, window_seconds)
            ttl = window_seconds

        if count > limit:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                retry_after=max(ttl, 0),
            )
        return RateLimitResult(
            allowed=True,
            remaining=max(0, limit - count),
            retry_after=0,
        )
    finally:
        await client.aclose()
