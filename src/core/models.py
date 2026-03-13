import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Site(TimestampMixin, Base):
    """Discovered Experience Cloud site."""

    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    cname_target: Mapped[str | None] = mapped_column(String(255))
    discovery_source: Mapped[str | None] = mapped_column(String(50))
    discovery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer)
    http_redirect_target: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    last_validated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assessment_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)

    assessments: Mapped[list["Assessment"]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )
    prospect: Mapped["Prospect | None"] = relationship(
        back_populates="site", uselist=False, cascade="all, delete-orphan"
    )


class Assessment(Base):
    """Assessment result per site per scan."""

    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    risk_score: Mapped[int | None] = mapped_column(
        Integer, CheckConstraint("risk_score >= 0 AND risk_score <= 100")
    )
    severity: Mapped[str | None] = mapped_column(String(20), index=True)
    checks: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    remediation_summary: Mapped[list[str] | None] = mapped_column(JSONB)
    scan_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    site: Mapped["Site"] = relationship(back_populates="assessments")


class Prospect(TimestampMixin, Base):
    """Enriched prospect data for a discovered site."""

    __tablename__ = "prospects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    company_name: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(100))
    employee_count: Mapped[int | None] = mapped_column(Integer)
    estimated_revenue: Mapped[str | None] = mapped_column(String(50))
    salesforce_edition: Mapped[str | None] = mapped_column(String(50))
    enrichment_source: Mapped[str | None] = mapped_column(String(50))
    enrichment_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    site: Mapped["Site"] = relationship(back_populates="prospect")
    contacts: Mapped[list["ProspectContact"]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan"
    )
    outreach_records: Mapped[list["Outreach"]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan"
    )


class ProspectContact(Base):
    """Individual contacts within a prospect organization."""

    __tablename__ = "prospect_contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    prospect_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    prospect: Mapped["Prospect"] = relationship(back_populates="contacts")
    outreach_records: Mapped[list["Outreach"]] = relationship(back_populates="contact")


class Outreach(TimestampMixin, Base):
    """Outreach tracking per contact."""

    __tablename__ = "outreach"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    prospect_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prospect_contacts.id", ondelete="SET NULL")
    )
    channel: Mapped[str | None] = mapped_column(String(20))
    template_used: Mapped[str | None] = mapped_column(String(100))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    prospect: Mapped["Prospect"] = relationship(back_populates="outreach_records")
    contact: Mapped["ProspectContact | None"] = relationship(back_populates="outreach_records")


class ScanJob(TimestampMixin, Base):
    """Celery scan job tracking."""

    __tablename__ = "scan_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    job_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False, index=True)
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sites_processed: Mapped[int] = mapped_column(Integer, default=0)
    sites_total: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
