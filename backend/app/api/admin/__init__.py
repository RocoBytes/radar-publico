from fastapi import APIRouter

from app.api.admin.cuentas import router as cuentas_router
from app.api.admin.dashboard import router as dashboard_router

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(cuentas_router)
router.include_router(dashboard_router)
