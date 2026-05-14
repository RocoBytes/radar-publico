"""Router agregador de la API v1."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.empresa import router as empresa_router
from app.api.v1.health import router as health_router
from app.api.v1.intereses import router as intereses_router
from app.api.v1.licitaciones import router as licitaciones_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(licitaciones_router)
router.include_router(empresa_router)
router.include_router(intereses_router)
