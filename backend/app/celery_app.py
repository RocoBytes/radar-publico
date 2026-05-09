"""Entrypoint de Celery.

Configura el worker y el beat scheduler.
Las tareas se registran en app/tasks/.
"""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "radar_publico",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.sync_chilecompra",
        # Sprint 2+:
        # "app.tasks.embeddings",
        # "app.tasks.notifications",
    ],
)

celery_app.conf.update(
    # Serialización
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Zona horaria: UTC en el worker, conversión en presentación
    timezone="UTC",
    enable_utc=True,
    # Reintentos por defecto
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Regla de oro #29: toda tarea debe ser idempotente
    # task_acks_on_failure_or_timeout=False  # descomentear si necesitas rollback manual
)

# Beat schedule: sincronización cada 15 minutos (CLAUDE.md §6.3)
celery_app.conf.beat_schedule = {
    "sync-listado-diario": {
        "task": "tasks.sync_chilecompra.sync_listado_diario",
        "schedule": 900.0,  # 15 minutos en segundos
        "options": {"expires": 800},  # no ejecutar si llega tarde (overlap)
    },
}
