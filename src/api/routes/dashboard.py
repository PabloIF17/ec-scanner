from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.core.models import Assessment, Prospect, Site, ScanJob
from src.core.schemas import DashboardOverview, ScanJobResponse

router = APIRouter()

SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"]


@router.get("/overview", response_model=DashboardOverview)
async def get_overview(
    db: AsyncSession = Depends(get_db_session),
):
    """Pipeline overview statistics."""
    # Total sites
    total_result = await db.execute(select(func.count()).select_from(Site))
    total_sites = total_result.scalar_one()

    # Active sites
    active_result = await db.execute(
        select(func.count()).select_from(Site).where(Site.is_active == True)
    )
    active_sites = active_result.scalar_one()

    # Assessed sites
    assessed_result = await db.execute(
        select(func.count()).select_from(Site).where(Site.assessment_status == "complete")
    )
    assessed_sites = assessed_result.scalar_one()

    # Pending assessment
    pending_result = await db.execute(
        select(func.count()).select_from(Site).where(Site.assessment_status == "pending")
    )
    pending_assessment = pending_result.scalar_one()

    # Count by severity (from latest assessment per site)
    by_severity: dict[str, int] = {s: 0 for s in SEVERITIES}

    for severity in SEVERITIES:
        count_result = await db.execute(
            select(func.count())
            .select_from(Assessment)
            .where(Assessment.severity == severity)
        )
        by_severity[severity] = count_result.scalar_one()

    # Recent scan jobs
    recent_jobs_result = await db.execute(
        select(ScanJob).order_by(ScanJob.created_at.desc()).limit(5)
    )
    recent_scans = [
        ScanJobResponse.model_validate(j) for j in recent_jobs_result.scalars().all()
    ]

    return DashboardOverview(
        total_sites=total_sites,
        active_sites=active_sites,
        assessed_sites=assessed_sites,
        pending_assessment=pending_assessment,
        by_severity=by_severity,
        recent_scans=recent_scans,
    )


@router.get("/high-priority")
async def get_high_priority(
    db: AsyncSession = Depends(get_db_session),
):
    """Sites scored >= 70 (HIGH or CRITICAL) with enrichment status."""
    result = await db.execute(
        select(Assessment, Site)
        .join(Site, Assessment.site_id == Site.id)
        .where(Assessment.risk_score >= 70)
        .where(Site.is_excluded == False)
        .order_by(Assessment.risk_score.desc())
        .limit(100)
    )

    items = []
    for assessment, site in result.all():
        item = {
            "site_id": str(site.id),
            "domain": site.domain,
            "risk_score": assessment.risk_score,
            "severity": assessment.severity,
            "assessment_date": assessment.assessment_date.isoformat(),
            "remediation_summary": assessment.remediation_summary,
        }
        items.append(item)

    return {"items": items, "total": len(items)}


@router.get("/trends")
async def get_trends(
    db: AsyncSession = Depends(get_db_session),
):
    """Time-series data for site discovery and assessment trends."""
    # Sites discovered per day over last 30 days
    result = await db.execute(
        select(
            func.date_trunc("day", Site.created_at).label("date"),
            func.count().label("count"),
        )
        .group_by(func.date_trunc("day", Site.created_at))
        .order_by(func.date_trunc("day", Site.created_at).desc())
        .limit(30)
    )

    trends = [
        {
            "date": row.date.date().isoformat(),
            "sites_discovered": row.count,
        }
        for row in result.all()
    ]

    return {"trends": trends}
