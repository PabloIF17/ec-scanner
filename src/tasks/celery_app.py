from celery import Celery

from src.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ec_scanner",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "src.tasks.discovery_tasks",
        "src.tasks.assessment_tasks",
        "src.tasks.enrichment_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "src.tasks.discovery_tasks.*": {"queue": "discovery"},
        "src.tasks.assessment_tasks.*": {"queue": "assessment"},
        "src.tasks.enrichment_tasks.*": {"queue": "enrichment"},
    },
    beat_schedule={
        "weekly-discovery": {
            "task": "src.tasks.discovery_tasks.run_full_discovery",
            "schedule": 604800.0,  # Every 7 days
            "options": {"queue": "discovery"},
        },
        "daily-assessment-new-sites": {
            "task": "src.tasks.assessment_tasks.assess_pending_sites",
            "schedule": 86400.0,  # Every 24 hours
            "options": {"queue": "assessment"},
        },
    },
)
