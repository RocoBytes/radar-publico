"""Entrypoint de la aplicación FastAPI.

Levanta la API, configura middleware, registra routers.
"""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.api.admin import router as admin_router
from app.api.v1 import router as v1_router
from app.api.v1.health import router as health_router
from app.config import settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida de la aplicación: startup y shutdown."""
    logger.info("iniciando_radar_publico", environment=settings.environment)
    yield
    logger.info("deteniendo_radar_publico")


app = FastAPI(
    title="Radar Público API",
    description="API de inteligencia comercial sobre el Mercado Público de Chile.",
    version="0.1.0",
    lifespan=lifespan,
    # En producción, deshabilitar Swagger y ReDoc
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

@app.middleware("http")
async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


# === CORS ===
# Regla de oro #7: CORS estricto, nunca wildcard en producción
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# === Routers ===
# /health en root para el healthcheck de Docker Compose (docker-compose.yml:100)
app.include_router(health_router)
# /api/v1/* incluye health + auth
app.include_router(v1_router, prefix="/api/v1")
# /api/admin/* — panel de administración
app.include_router(admin_router, prefix="/api")
