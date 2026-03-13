import uuid

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.core.models import ScanJob
from src.core.schemas import ScanJobCreate, ScanJobResponse, ScanStatusResponse
from src.tasks.celery_app import celery_app

router = APIRouter()


@router.get("", response_model=list[ScanJobResponse])
async def list_scans(
    status: str | None = None,
    job_type: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    """List scan jobs."""
    stmt = select(ScanJob).order_by(ScanJob.created_at.desc())

    if status:
        stmt = stmt.where(ScanJob.status == status)
    if job_type:
        stmt = stmt.where(ScanJob.job_type == job_type)

    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    return [ScanJobResponse.model_validate(j) for j in jobs]


@router.post("/discovery", status_code=202)
async def trigger_discovery_scan(
    db: AsyncSession = Depends(get_db_session),
):
    """Trigger a full discovery scan."""
    from src.tasks.discovery_tasks import run_full_discovery

    task = run_full_discovery.apply_async(queue="discovery")

    job = ScanJob(
        id=uuid.uuid4(),
        celery_task_id=task.id,
        job_type="discovery",
        status="queued",
    )
    db.add(job)
    await db.flush()

    return {
        "job_id": str(job.id),
        "celery_task_id": task.id,
        "status": "queued",
        "message": "Discovery scan queued",
    }


@router.post("/assessment", status_code=202)
async def trigger_assessment_scan(
    data: ScanJobCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """Trigger assessment scan for specific sites or all pending sites."""
    from src.tasks.assessment_tasks import assess_site, assess_pending_sites

    if data.site_id:
        task = assess_site.apply_async(args=[str(data.site_id)], queue="assessment")
        job = ScanJob(
            id=uuid.uuid4(),
            celery_task_id=task.id,
            job_type="assessment",
            status="queued",
            site_id=data.site_id,
        )
    elif data.site_ids:
        task = None
        for site_id in data.site_ids:
            assess_site.apply_async(args=[str(site_id)], queue="assessment")
        job = ScanJob(
            id=uuid.uuid4(),
            job_type="assessment",
            status="queued",
            sites_total=len(data.site_ids),
        )
    else:
        task = assess_pending_sites.apply_async(queue="assessment")
        job = ScanJob(
            id=uuid.uuid4(),
            celery_task_id=task.id if task else None,
            job_type="assessment",
            status="queued",
        )

    db.add(job)
    await db.flush()

    return {
        "job_id": str(job.id),
        "celery_task_id": job.celery_task_id,
        "status": "queued",
        "message": "Assessment scan queued",
    }


@router.get("/{job_id}/status", response_model=ScanStatusResponse)
async def get_scan_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get real-time status of a scan job."""
    result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")

    # Get live status from Celery if task_id is set
    celery_status = job.status
    progress = 0
    phase = None

    if job.celery_task_id:
        celery_result = AsyncResult(job.celery_task_id, app=celery_app)
        state = celery_result.state

        if state == "PROGRESS":
            info = celery_result.info or {}
            progress = info.get("progress", 0)
            phase = info.get("phase")
            celery_status = "running"
        elif state == "SUCCESS":
            celery_status = "complete"
            progress = 100
        elif state == "FAILURE":
            celery_status = "failed"
        elif state == "PENDING":
            celery_status = "queued"

    return ScanStatusResponse(
        job_id=job_id,
        celery_task_id=job.celery_task_id,
        status=celery_status,
        progress_pct=progress,
        phase=phase,
        sites_processed=job.sites_processed,
        sites_total=job.sites_total,
        error_message=job.error_message,
    )
