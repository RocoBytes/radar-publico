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
        "app.tasks.sync_detalle",  # Sprint 2: detalle de licitaciones
        "app.tasks.scrape_bases",  # Sprint 2: scraping de PDFs desde el portal
        "app.tasks.procesar_pdf",  # Sprint 2: parseo + chunking de PDFs
        "app.tasks.embed_chunks",  # Sprint 2: embeddings de chunks con Voyage
        "app.tasks.embed_licitacion",  # Sprint 2: embedding de licitación (título+desc)
        "app.tasks.marcar_procesada",  # Sprint 2: marcar licitación procesada
        "app.tasks.recalcula_scores",  # Sprint 4: scoring de relevancia
        "app.tasks.ejecuta_radares",  # Sprint 4: ejecucion de radares
        "app.tasks.procesar_notificaciones",  # Sprint 5: despacho de notificaciones
        "app.tasks.generar_recordatorios",  # Sprint 5: recordatorios de cierre
        "app.tasks.detecta_renovaciones",  # Sprint 6: feed de renovaciones
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
    # Routing: tareas de scraping van a la queue dedicada (worker con browsers)
    task_routes={
        # scraping y parseo PDF → worker con browsers + pymupdf
        "tasks.scrape_bases.*": {"queue": "scraping"},
        "tasks.procesar_pdf.*": {"queue": "scraping"},
        # embeddings → cola default (I/O HTTP puro a Voyage)
        "tasks.embed_chunks.*": {"queue": "celery"},
        "tasks.embed_licitacion.*": {"queue": "celery"},
        "tasks.marcar_procesada.*": {"queue": "celery"},
    },
)

# Beat schedule: sincronización cada 15 minutos (CLAUDE.md §6.3)
celery_app.conf.beat_schedule = {
    "sync-listado-diario": {
        "task": "tasks.sync_chilecompra.sync_listado_diario",
        "schedule": 900.0,  # 15 minutos en segundos
        "options": {"expires": 800},
    },
    "ejecuta-radares-diarios": {
        "task": "tasks.ejecuta_radares.ejecuta_radares_diarios",
        "schedule": 900.0,  # cada 15 min, encadenado al sync
        "options": {"expires": 800},
    },
    "procesar-notificaciones": {
        "task": "tasks.procesar_notificaciones.procesar_notificaciones",
        "schedule": 300.0,  # cada 5 minutos
        "options": {"expires": 280},
    },
    "generar-recordatorios-cierre": {
        "task": "tasks.generar_recordatorios.generar_recordatorios_cierre",
        "schedule": 3600.0,  # cada hora
        "options": {"expires": 3500},
    },
    "detecta-renovaciones": {
        "task": "tasks.detecta_renovaciones.detecta_renovaciones",
        "schedule": 86400.0,  # una vez al día
        "options": {"expires": 85000},
    },
}
