"""
Enrichment Pipeline

For each site with risk_score >= 50 (MEDIUM+), enriches with firmographic data.
Sources: Clearbit → ZoomInfo → Apollo (in priority order, first success wins).
"""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Assessment, Prospect, Site

logger = structlog.get_logger(__name__)


class EnrichmentPipeline:
    """Orchestrates prospect enrichment from multiple data sources."""

    def __init__(self) -> None:
        self.log = structlog.get_logger(__name__)

    async def run(self, site_id: uuid.UUID, db: AsyncSession) -> dict:
        """Enrich a site with firmographic data."""
        # Get site and its latest assessment
        site_result = await db.execute(select(Site).where(Site.id == site_id))
        site = site_result.scalar_one_or_none()
        if not site:
            return {"error": "Site not found"}

        assessment_result = await db.execute(
            select(Assessment)
            .where(Assessment.site_id == site_id)
            .order_by(Assessment.assessment_date.desc())
            .limit(1)
        )
        assessment = assessment_result.scalar_one_or_none()

        if not assessment or (assessment.risk_score or 0) < 50:
            return {"skipped": "Risk score below MEDIUM threshold"}

        # Extract company from domain
        domain_parts = site.domain.split(".")
        company_guess = domain_parts[0] if len(domain_parts) > 1 else site.domain

        # Check if prospect already exists
        existing = await db.execute(
            select(Prospect).where(Prospect.site_id == site_id)
        )
        prospect = existing.scalar_one_or_none()

        if not prospect:
            prospect = Prospect(
                id=uuid.uuid4(),
                site_id=site_id,
                company_name=company_guess,
                enrichment_source="domain_guess",
            )
            db.add(prospect)

        # TODO: Integrate Clearbit/ZoomInfo/Apollo APIs when keys are configured
        # For now, log that enrichment needs API keys
        self.log.info(
            "enrichment.pending_api_keys",
            domain=site.domain,
            risk_score=assessment.risk_score,
        )

        await db.flush()
        return {
            "status": "partial",
            "domain": site.domain,
            "note": "Configure CLEARBIT_API_KEY, ZOOMINFO_API_KEY, or APOLLO_API_KEY for full enrichment",
        }
