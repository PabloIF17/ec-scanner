import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.core.models import Assessment
from src.core.schemas import AssessmentResponse

router = APIRouter()


@router.get("", response_model=list[AssessmentResponse])
async def list_assessments(
    severity: str | None = None,
    min_score: int | None = Query(None, ge=0, le=100),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
):
    """List assessments with optional filters."""
    stmt = select(Assessment).order_by(Assessment.assessment_date.desc())

    if severity:
        stmt = stmt.where(Assessment.severity == severity.upper())
    if min_score is not None:
        stmt = stmt.where(Assessment.risk_score >= min_score)

    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    assessments = result.scalars().all()
    return [AssessmentResponse.model_validate(a) for a in assessments]


@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get assessment details by ID."""
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return AssessmentResponse.model_validate(assessment)
