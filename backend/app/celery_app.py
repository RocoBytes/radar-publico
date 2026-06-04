"""Entrypoint de Celery.

Configura el worker y el beat scheduler.
Las tareas se registran en app/tasks/.
"""

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_prerun
import structlog

from app.config import settings

celery_app = Celery(
    "radar_publico",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.sync_chilecompra",
        "app.tasks.notifications",  # Feature B: alertas cambio estado externo
        "app.tasks.sync_detalle",  # Sprint 2: detalle de licitaciones
        "app.tasks.scrape_bases",  # Sprint 2: scraping de PDFs desde el portal
        "app.tasks.procesar_pdf",  # Sprint 2: parseo + chunking de PDFs
        "app.tasks.embed_chunks",  # Sprint 2: embeddings de chunks con Voyage
        "app.tasks.embed_licitacion",  # Sprint 2: embedding de licitación (título+desc)
        "app.tasks.marcar_procesada",  # Sprint 2: marcar licitación procesada
        "app.tasks.analizar_bases",  # Plan 0 IA: análisis LLM de bases técnicas
        "app.tasks.generar_borrador",  # Módulo 2 IA: borrador de propuesta técnica
        "app.tasks.recalcula_scores",  # Sprint 4: scoring de relevancia
        "app.tasks.ejecuta_radares",  # Sprint 4: ejecucion de radares
        "app.tasks.procesar_notificaciones",  # Sprint 5: despacho de notificaciones
        "app.tasks.generar_recordatorios",  # Sprint 5: recordatorios de cierre
        "app.tasks.detecta_renovaciones",  # Sprint 6: feed de renovaciones
        "app.tasks.sync_plan_anual",  # Sprint 6: plan anual de compras
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
@task_prerun.connect  # type: ignore[misc]
def reset_db_pool_before_task(**kwargs: object) -> None:
    """Descarta el pool asyncpg ANTES de cada tarea para evitar 'Future attached to different loop'.

    Cada asyncio.run() crea un event loop nuevo. El pool asyncpg (del task anterior) quedó atado
    al loop anterior. engine.sync_engine.dispose() lo descarta de forma síncrona, sin necesitar
    un loop nuevo. El próximo asyncio.run() creará conexiones frescas en su propio loop.
    """
    try:
        from app.db.session import engine

        engine.sync_engine.dispose()
    except Exception:
        structlog.get_logger().warning("dispose_db_pool_failed")


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
    # Ventana nocturna CLT (22:00-07:00 = 01:00-10:00 UTC).
    # Encola 500 detalles por hora → hasta 4.500 en 9 horas sin tocar cuota diurna.
    "sync-detalles-pendientes-noche": {
        "task": "tasks.sync_detalle.sync_detalles_pendientes",
        "schedule": crontab(minute=0, hour="1-9"),  # 01:00-09:00 UTC cada hora
        "kwargs": {"limit": 500},
        "options": {"expires": 3500},
    },
    # Plan Anual de Compras: día 6 de cada mes a las 02:00 UTC
    # = 23:00 CLT invierno (UTC-3) / 22:00 CLT verano (UTC-4).
    # Ambos horarios están dentro de la ventana nocturna 22:00-07:00 CLT.
    "sync-plan-anual-mensual": {
        "task": "tasks.sync_plan_anual.sync_plan_anual",
        "schedule": crontab(hour=2, minute=0, day_of_month=6),
        "options": {"expires": 3500},
    },
}
