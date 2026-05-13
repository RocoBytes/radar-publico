from fastapi import APIRouter

from app.api.admin.cuentas import router as cuentas_router

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(cuentas_router)
