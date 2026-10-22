"""Queries over job postings and the audit log. Callers own the session/commit."""

from typing import Any

from sqlalchemy import Integer, func, literal_column, select
from sqlalchemy.orm import Session

from src.ingestion.base import RawJobPosting
from src.ingestion.deduplicator import content_key
from src.ingestion.scorer import JobScore
from src.storage.models import AuditLog, JobPosting, utcnow


def job_id(job: RawJobPosting) -> str:
    """Stable id derived from the content key, so re-sightings map to the same row."""
    return f"job_{content_key(job)[:8]}"


def upsert_job(session: Session, job: RawJobPosting, score: JobScore) -> JobPosting:
    """Insert a posting, or refresh (and reactivate) the one with the same content key."""
    key = content_key(job)
    row = session.scalar(select(JobPosting).where(JobPosting.content_key == key))
    if row is None:
        row = JobPosting(id=job_id(job), content_key=key, discovered_at=utcnow())
        session.add(row)
    row.title, row.company, row.location = job.title, job.company, job.location
    row.url, row.description, row.source = job.url, job.description, job.source
    row.posted_at = job.posted_at
    row.score, row.tier, row.boost = score.score, score.tier, score.boost
    row.is_active = True
    row.last_seen_at = utcnow()
    return row


def get_job(session: Session, job_id: str) -> JobPosting | None:
    return session.get(JobPosting, job_id)


def list_active(
    session: Session, min_score: int | None = None, active_only: bool = True
) -> list[JobPosting]:
    query = select(JobPosting).where(JobPosting.is_active) if active_only else select(JobPosting)
    if min_score is not None:
        query = query.where(JobPosting.score >= min_score)
    query = query.order_by(JobPosting.score.desc(), JobPosting.discovered_at)
    return list(session.scalars(query))


def mark_inactive(session: Session, job_id: str) -> None:
    row = get_job(session, job_id)
    if row is None:
        raise KeyError(job_id)
    row.is_active = False
    row.last_verified_at = utcnow()


def record_audit(
    session: Session,
    *,
    actor: str,
    action: str,
    status: str,
    target_id: str | None = None,
    duration_ms: int | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    event = AuditLog(
        actor=actor,
        action=action,
        status=status,
        target_id=target_id,
        duration_ms=duration_ms,
        details=details or {},
    )
    session.add(event)
    return event


def query_audit(
    session: Session,
    *,
    actor: str | None = None,
    action: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """Newest first; filters are optional exact matches."""
    query = select(AuditLog)
    for column, value in (
        (AuditLog.actor, actor),
        (AuditLog.action, action),
        (AuditLog.status, status),
    ):
        if value is not None:
            query = query.where(column == value)
    # rowid breaks ties between events logged within the same microsecond.
    query = (
        query.order_by(AuditLog.timestamp.desc(), literal_column("rowid").desc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(query))


def latest_audit_rowid(session: Session) -> int:
    """SQLite rowids only grow, so they work as a cursor for new audit events."""
    latest = session.scalar(select(func.max(literal_column("rowid"))).select_from(AuditLog))
    return int(latest or 0)


def audit_after(session: Session, rowid: int, limit: int = 500) -> list[tuple[int, AuditLog]]:
    """Audit events inserted after `rowid`, oldest first, with their rowids."""
    rid = literal_column("rowid", Integer)
    rows = session.execute(select(rid, AuditLog).where(rid > rowid).order_by(rid).limit(limit))
    return [(int(r[0]), r[1]) for r in rows]
