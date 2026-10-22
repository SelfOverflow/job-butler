"""ORM tables. Timestamps are naive UTC (SQLite has no time zone type)."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    content_key: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str]
    company: Mapped[str]
    location: Mapped[str]
    url: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50))
    posted_at: Mapped[datetime | None]
    score: Mapped[int]
    tier: Mapped[str | None]
    boost: Mapped[int]
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    discovered_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_verified_at: Mapped[datetime | None]


class AuditLog(Base):
    """Ledger of every agent and human action (see docs/architecture.md §7.1)."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    timestamp: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(50), index=True)  # e.g. agent:scout, human:user
    action: Mapped[str] = mapped_column(String(50), index=True)  # e.g. JOB_DISCOVERED
    target_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))  # SUCCESS | WARNING | FAILURE
    duration_ms: Mapped[int | None]
    # `metadata` is reserved by SQLAlchemy's declarative base, hence the attribute name.
    details: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


class ApplicationStatus(StrEnum):
    NEEDS_INPUT = "needs_input"  # Required questions the profile cannot answer.
    BLOCKED = "blocked"  # Login/account, CAPTCHA, or 2FA barrier.
    AWAITING_REVIEW = "awaiting_review"  # Filled; waiting for the candidate to approve.
    SUBMITTED = "submitted"
    APPLIED_MANUALLY = "applied_manually"
    SKIPPED = "skipped"
    FAILED = "failed"


PENDING_STATUSES = (
    ApplicationStatus.NEEDS_INPUT,
    ApplicationStatus.BLOCKED,
    ApplicationStatus.AWAITING_REVIEW,
)


class ApplicationRecord(Base):
    """One application per job. Submission only ever follows explicit human approval."""

    __tablename__ = "applications"

    job_id: Mapped[str] = mapped_column(ForeignKey("job_postings.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    barrier: Mapped[str | None] = mapped_column(String(40))
    plan: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)  # Field -> value.
    # Unanswered required fields: [{label, kind, options}] so the UI can render inputs.
    questions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    answers: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)  # From the candidate.
    screenshot: Mapped[str | None]
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, index=True)
    submitted_at: Mapped[datetime | None]

    job: Mapped[JobPosting] = relationship(lazy="joined")


class MarketSnapshotRecord(Base):
    """Technology demand and upskilling ROI across one sweep's eligible postings."""

    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    total: Mapped[int]  # Gate-passing postings analysed.
    matched: Mapped[int]  # Of those, scoring at or above `threshold`.
    threshold: Mapped[int]
    demand: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    upskill: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class CommandStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CommandRun(Base):
    """Background operation launched from the command center (see slice 8)."""

    __tablename__ = "command_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    command: Mapped[str] = mapped_column(String(50), index=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default=CommandStatus.QUEUED, index=True)
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(String(50), default="human:user")
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
