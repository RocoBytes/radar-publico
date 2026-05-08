"""Entrypoint de la aplicación FastAPI.

Levanta la API, configura middleware, registra routers.
"""

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# === CORS ===
# Regla de oro #7: CORS estricto, nunca wildcard en producción
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# === Healthcheck ===
# Regla de oro #27: /health retorna estado de Postgres, Redis y workers
@app.get("/health", tags=["sistema"])
async def health() -> dict[str, object]:
    """Verificación de salud del sistema.

    Retorna el estado de los componentes críticos.
    En Sprint 1 se conectará a Postgres y Redis reales.
    """
    return {
        "status": "ok",
        "timestamp": time.time(),
        "environment": settings.environment,
        "version": "0.1.0",
        "components": {
            "postgres": "not_checked",
            "redis": "not_checked",
            "workers": "not_checked",
        },
    }


# === Routers (se agregan en Sprint 1+) ===
# from app.api.v1 import router as v1_router
# from app.api.admin import router as admin_router
# app.include_router(v1_router, prefix="/api/v1")
# app.include_router(admin_router, prefix="/api/admin")
