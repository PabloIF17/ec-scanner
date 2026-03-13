import asyncio
import uuid

import structlog
from sqlalchemy import select

from src.core.database import AsyncSessionLocal
from src.core.models import Site
from src.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    name="src.tasks.assessment_tasks.assess_site",
    max_retries=3,
    default_retry_delay=120,
)
def assess_site(self, site_id: str):
    """Run assessment pipeline for a single site."""

    async def _run():
        from src.assessment.pipeline import AssessmentPipeline

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Site).where(Site.id == uuid.UUID(site_id))
            )
            site = result.scalar_one_or_none()
            if not site:
                return {"error": f"Site {site_id} not found"}

            site.assessment_status = "in_progress"
            await db.flush()

            pipeline = AssessmentPipeline()
            assessment = await pipeline.run(site, db)

            return {
                "status": "completed",
                "assessment_id": str(assessment.id),
                "risk_score": assessment.risk_score,
                "severity": assessment.severity,
            }

    self.update_state(state="PROGRESS", meta={"phase": "assessment", "site_id": site_id})

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("assessment_task.failed", site_id=site_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="src.tasks.assessment_tasks.assess_pending_sites",
    max_retries=1,
)
def assess_pending_sites(self, limit: int = 100):
    """Assess all sites with assessment_status='pending'. Scheduled daily."""

    async def _get_pending():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Site)
                .where(Site.assessment_status == "pending")
                .where(Site.is_active == True)
                .where(Site.is_excluded == False)
                .limit(limit)
            )
            return [str(s.id) for s in result.scalars().all()]

    try:
        site_ids = asyncio.run(_get_pending())
        logger.info("assess_pending.dispatching", count=len(site_ids))

        for site_id in site_ids:
            assess_site.apply_async(args=[site_id], queue="assessment")

        return {"status": "dispatched", "count": len(site_ids)}
    except Exception as exc:
        logger.error("assess_pending.failed", error=str(exc))
        raise
