import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.core.models import Prospect
from src.core.schemas import ProspectResponse

router = APIRouter()


@router.get("", response_model=list[ProspectResponse])
async def list_prospects(
    industry: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
):
    """List enriched prospects."""
    stmt = (
        select(Prospect)
        .options(selectinload(Prospect.contacts))
        .order_by(Prospect.created_at.desc())
    )

    if industry:
        stmt = stmt.where(Prospect.industry.ilike(f"%{industry}%"))

    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    prospects = result.scalars().all()
    return [ProspectResponse.model_validate(p) for p in prospects]


@router.get("/{prospect_id}", response_model=ProspectResponse)
async def get_prospect(
    prospect_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get prospect details with contacts."""
    result = await db.execute(
        select(Prospect)
        .options(selectinload(Prospect.contacts))
        .where(Prospect.id == prospect_id)
    )
    prospect = result.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return ProspectResponse.model_validate(prospect)


@router.post("/{prospect_id}/enrich", status_code=202)
async def trigger_enrichment(
    prospect_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Trigger manual enrichment for a prospect."""
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    from src.tasks.enrichment_tasks import enrich_prospect
    task = enrich_prospect.apply_async(args=[str(prospect.site_id)], queue="enrichment")

    return {"task_id": task.id, "prospect_id": str(prospect_id), "status": "queued"}
