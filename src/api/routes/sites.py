import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.core.models import Assessment, Site
from src.core.schemas import AssessmentResponse, SiteCreate, SiteList, SiteResponse, SiteUpdate

router = APIRouter()


@router.get("", response_model=SiteList)
async def list_sites(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    severity: str | None = None,
    is_active: bool | None = None,
    assessment_status: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    """List all discovered sites with optional filtering."""
    stmt = select(Site)

    if is_active is not None:
        stmt = stmt.where(Site.is_active == is_active)
    if assessment_status:
        stmt = stmt.where(Site.assessment_status == assessment_status)

    # Filter by severity requires joining with assessments
    if severity:
        latest_assessment = (
            select(Assessment.site_id, Assessment.severity)
            .distinct(Assessment.site_id)
            .order_by(Assessment.site_id, Assessment.assessment_date.desc())
            .subquery()
        )
        stmt = stmt.join(latest_assessment, Site.id == latest_assessment.c.site_id)
        stmt = stmt.where(latest_assessment.c.severity == severity.upper())

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Paginate
    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    sites = result.scalars().all()

    return SiteList(
        items=[SiteResponse.model_validate(s) for s in sites],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{site_id}", response_model=SiteResponse)
async def get_site(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get a specific site by ID."""
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return SiteResponse.model_validate(site)


@router.post("", response_model=SiteResponse, status_code=201)
async def create_site(
    data: SiteCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """Manually add a site for discovery/assessment."""
    # Check for duplicates
    existing = await db.execute(select(Site).where(Site.domain == data.domain))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Site with this domain already exists")

    site = Site(
        id=uuid.uuid4(),
        domain=data.domain.lower().strip(),
        cname_target=data.cname_target,
        discovery_source=data.discovery_source or "manual",
        assessment_status="pending",
    )
    db.add(site)
    await db.flush()
    return SiteResponse.model_validate(site)


@router.patch("/{site_id}", response_model=SiteResponse)
async def update_site(
    site_id: uuid.UUID,
    data: SiteUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update site fields."""
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(site, key, value)

    await db.flush()
    return SiteResponse.model_validate(site)


@router.post("/{site_id}/exclude", response_model=SiteResponse)
async def exclude_site(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Mark a site as excluded from scans."""
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    site.is_excluded = True
    await db.flush()
    return SiteResponse.model_validate(site)


@router.post("/{site_id}/assess")
async def trigger_assessment(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Trigger a manual assessment for a specific site."""
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    from src.tasks.assessment_tasks import assess_site
    task = assess_site.apply_async(args=[str(site_id)], queue="assessment")

    return {"task_id": task.id, "site_id": str(site_id), "status": "queued"}


@router.get("/{site_id}/assessments", response_model=list[AssessmentResponse])
async def get_site_assessments(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get all assessments for a specific site."""
    result = await db.execute(
        select(Assessment)
        .where(Assessment.site_id == site_id)
        .order_by(Assessment.assessment_date.desc())
    )
    assessments = result.scalars().all()
    return [AssessmentResponse.model_validate(a) for a in assessments]
