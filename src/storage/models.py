"""ORM tables. Timestamps are naive UTC (SQLite has no time zone type)."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
