"""Engine y session factory de SQLAlchemy async.

Uso:
    async with get_session() as session:
        resultado = await session.execute(select(Usuario))

Pool sizing:
  API  → pool_size=10, max_overflow=20 (sirve muchas requests concurrentes)
  Worker → pool_size=2, max_overflow=3  (una tarea a la vez por proceso ForkPool)

Sin esta distinción, 4 workers x 30 conexiones + scraper x 30 + API x 30
supera fácilmente el max_connections=100 de Postgres bajo carga.
"""

from collections.abc import AsyncGenerator
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# En contexto Celery cada proceso ejecuta una tarea a la vez — pool chico.
# La variable CELERY_WORKER_RUNNING la setea celery_app.py en worker_init.
_en_worker = os.environ.get("CELERY_WORKER_RUNNING") == "1"

engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
    pool_size=2 if _en_worker else 10,
    max_overflow=3 if _en_worker else 20,
)

# Factory de sesiones
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia FastAPI que provee una sesión de base de datos."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
