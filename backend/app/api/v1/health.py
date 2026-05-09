"""Endpoint /health mejorado.

Regla de oro #27: /health retorna estado de Postgres, Redis y workers.
- 200 si todos los componentes críticos están OK.
- 503 si algún componente crítico falla (Postgres o Redis).
- Workers y última sync son informativos (no bloquean el 200/503).
"""

import time
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
import structlog

from app.db.session import AsyncSessionLocal

logger = structlog.get_logger()

router = APIRouter()

ComponentStatus = Literal["ok", "error", "not_checked"]


async def _check_postgres() -> tuple[ComponentStatus, str | None]:
    """Verifica conectividad con Postgres ejecutando un query trivial."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return "ok", None
    except Exception as e:
        logger.error("health_postgres_failed", error=str(e))
        return "error", str(e)


async def _check_redis() -> tuple[ComponentStatus, str | None]:
    """Verifica conectividad con Redis con un PING."""
    try:
        import redis.asyncio as aioredis

        from app.config import settings

        client = aioredis.from_url(settings.redis_url, socket_timeout=2.0)
        await client.ping()
        await client.aclose()
        return "ok", None
    except Exception as e:
        logger.error("health_redis_failed", error=str(e))
        return "error", str(e)


async def _check_celery() -> tuple[ComponentStatus, str | None]:
    """Verifica que haya al menos un worker Celery activo."""
    try:
        # inspect().ping() es síncrono en Celery — ejecutar en threadpool
        import asyncio

        from app.celery_app import celery_app

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: celery_app.control.inspect(timeout=2.0).ping(),
        )
        if result:
            return "ok", None
        return "error", "Sin workers activos"
    except Exception as e:
        logger.warning("health_celery_check_failed", error=str(e))
        return "error", str(e)


async def _last_sync() -> str | None:
    """Retorna la fecha de la última licitación sincronizada."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    "SELECT MAX(detalle_sincronizado_at) "
                    "FROM licitaciones "
                    "WHERE detalle_sincronizado_at IS NOT NULL"
                )
            )
            row = result.scalar_one_or_none()
            return row.isoformat() if row else None
    except Exception:
        return None


@router.get("/health", tags=["sistema"])
async def health() -> JSONResponse:
    """Verificación de salud del sistema.

    Comprueba Postgres, Redis y Celery workers.
    Retorna 200 si los componentes críticos (Postgres + Redis) están OK.
    Retorna 503 si alguno falla.
    """
    pg_status, pg_error = await _check_postgres()
    redis_status, redis_error = await _check_redis()
    celery_status, celery_error = await _check_celery()
    ultima_sync = await _last_sync()

    # Componentes críticos: Postgres y Redis
    is_healthy = pg_status == "ok" and redis_status == "ok"
    http_status = 200 if is_healthy else 503

    from app.config import settings as _settings

    pg_info: dict[str, object] = {"status": pg_status}
    if pg_error:
        pg_info["error"] = pg_error
    redis_info: dict[str, object] = {"status": redis_status}
    if redis_error:
        redis_info["error"] = redis_error
    celery_info: dict[str, object] = {"status": celery_status}
    if celery_error:
        celery_info["error"] = celery_error

    payload: dict[str, object] = {
        "status": "ok" if is_healthy else "degraded",
        "timestamp": time.time(),
        "environment": _settings.environment,
        "components": {
            "postgres": pg_info,
            "redis": redis_info,
            "celery": celery_info,
        },
        "ultima_sincronizacion_chilecompra": ultima_sync,
    }

    return JSONResponse(content=payload, status_code=http_status)
