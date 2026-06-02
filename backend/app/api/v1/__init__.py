"""Router agregador de la API v1."""

from fastapi import APIRouter

from app.api.v1.analisis import router as analisis_router
from app.api.v1.auth import router as auth_router
from app.api.v1.catalogos import router as catalogos_router
from app.api.v1.chat import router as chat_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.directorios import router as directorios_router
from app.api.v1.empresa import router as empresa_router
from app.api.v1.futuro import router as futuro_router
from app.api.v1.health import router as health_router
from app.api.v1.inteligencia import router as inteligencia_router
from app.api.v1.intereses import router as intereses_router
from app.api.v1.licitaciones import router as licitaciones_router
from app.api.v1.notificaciones import router as notificaciones_router
from app.api.v1.pipeline import router as pipeline_router
from app.api.v1.preferencias import router as preferencias_router
from app.api.v1.radares import router as radares_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(catalogos_router)
router.include_router(licitaciones_router)
router.include_router(analisis_router)
router.include_router(inteligencia_router)
router.include_router(empresa_router)
router.include_router(intereses_router)
router.include_router(radares_router)
router.include_router(pipeline_router)
router.include_router(dashboard_router)
router.include_router(futuro_router)
router.include_router(notificaciones_router)
router.include_router(preferencias_router)
router.include_router(directorios_router)
router.include_router(chat_router, prefix="/chat", tags=["chat"])
