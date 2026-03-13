import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


# ─── Site Schemas ──────────────────────────────────────────────────────────────

class SiteCreate(BaseModel):
    domain: str
    cname_target: str | None = None
    discovery_source: str | None = None


class SiteUpdate(BaseModel):
    cname_target: str | None = None
    is_active: bool | None = None
    is_excluded: bool | None = None
    assessment_status: str | None = None


class SiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    domain: str
    cname_target: str | None
    discovery_source: str | None
    discovery_date: datetime | None
    http_status: int | None
    is_active: bool
    is_excluded: bool
    last_validated: datetime | None
    assessment_status: str
    created_at: datetime
    updated_at: datetime


class SiteList(BaseModel):
    items: list[SiteResponse]
    total: int
    page: int
    size: int


# ─── Assessment Schemas ────────────────────────────────────────────────────────

class AssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    assessment_date: datetime
    risk_score: int | None
    severity: str | None
    checks: dict[str, Any]
    remediation_summary: list[str] | None
    scan_duration_seconds: int | None
    error_message: str | None
    created_at: datetime


# ─── Scan Job Schemas ──────────────────────────────────────────────────────────

class ScanJobCreate(BaseModel):
    job_type: str
    site_id: uuid.UUID | None = None
    site_ids: list[uuid.UUID] | None = None


class ScanJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    celery_task_id: str | None
    job_type: str
    status: str
    site_id: uuid.UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    sites_processed: int
    sites_total: int
    error_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ScanStatusResponse(BaseModel):
    job_id: uuid.UUID
    celery_task_id: str | None
    status: str
    progress_pct: int = 0
    phase: str | None = None
    sites_processed: int = 0
    sites_total: int = 0
    error_message: str | None = None


# ─── Prospect Schemas ──────────────────────────────────────────────────────────

class ProspectContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    title: str | None
    email: str | None
    linkedin_url: str | None
    source: str | None


class ProspectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    company_name: str | None
    industry: str | None
    employee_count: int | None
    estimated_revenue: str | None
    salesforce_edition: str | None
    enrichment_source: str | None
    created_at: datetime
    contacts: list[ProspectContactResponse] = []


# ─── Dashboard Schemas ─────────────────────────────────────────────────────────

class DashboardOverview(BaseModel):
    total_sites: int
    active_sites: int
    assessed_sites: int
    pending_assessment: int
    by_severity: dict[str, int]
    recent_scans: list[ScanJobResponse]


class DashboardTrend(BaseModel):
    date: str
    sites_discovered: int
    sites_assessed: int
    critical_count: int
    high_count: int
