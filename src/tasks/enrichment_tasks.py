import asyncio
import uuid

import structlog

from src.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    name="src.tasks.enrichment_tasks.enrich_prospect",
    max_retries=3,
    default_retry_delay=300,
)
def enrich_prospect(self, site_id: str):
    """Enrich prospect data for a site that reached MEDIUM+ risk score."""

    async def _run():
        from src.enrichment.pipeline import EnrichmentPipeline
        from src.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            pipeline = EnrichmentPipeline()
            return await pipeline.run(uuid.UUID(site_id), db)

    self.update_state(state="PROGRESS", meta={"phase": "enrichment", "site_id": site_id})

    try:
        result = asyncio.run(_run())
        return result
    except Exception as exc:
        logger.error("enrichment_task.failed", site_id=site_id, error=str(exc))
        raise self.retry(exc=exc)
