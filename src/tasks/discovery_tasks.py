import asyncio

import structlog
from celery import states

from src.core.config import get_settings
from src.core.database import AsyncSessionLocal
from src.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    name="src.tasks.discovery_tasks.run_full_discovery",
    max_retries=3,
    default_retry_delay=60,
)
def run_full_discovery(self):
    """
    Full discovery pipeline — queries all data sources and persists new sites.
    Scheduled weekly via Celery Beat.
    """
    settings = get_settings()

    async def _run():
        from src.discovery.pipeline import DiscoveryPipeline

        async with AsyncSessionLocal() as db:
            pipeline = DiscoveryPipeline(settings)
            return await pipeline.run(db)

    self.update_state(state="PROGRESS", meta={"phase": "discovery", "progress": 0})

    try:
        summary = asyncio.run(_run())
        return {
            "status": "completed",
            "raw_discovered": summary.raw_discovered,
            "after_dedup": summary.after_dedup,
            "dns_resolved": summary.dns_resolved,
            "salesforce_confirmed": summary.salesforce_confirmed,
            "http_confirmed": summary.http_confirmed,
            "new_sites_saved": summary.new_sites_saved,
            "updated_sites": summary.updated_sites,
            "errors": summary.errors,
        }
    except Exception as exc:
        logger.error("discovery_task.failed", error=str(exc))
        raise self.retry(exc=exc)
