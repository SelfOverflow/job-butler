"""Scout service shared by the CLI and web API (see slice 8)."""

import httpx
from sqlalchemy.orm import Session

from src.ingestion.base import ProgressFn, format_unstructured_description, no_progress
from src.ingestion.firecrawl_client import FirecrawlClient
from src.ingestion.pipeline import SweepReport, prune_ineligible, run_sweep, verify_stored
from src.ingestion.verifier import verify as verifier_verify
from src.profile.models import CandidateProfile
from src.services.common import CancelToken
from src.storage import repository as repo
from src.storage.models import JobPosting, JobStatus, utcnow


class ScoutError(Exception):
    pass


def sweep(
    profile: CandidateProfile,
    session: Session,
    http: httpx.Client,
    firecrawl: FirecrawlClient | None,
    limit: int | None = 20,
    progress: ProgressFn = no_progress,
    cancel: CancelToken | None = None,
) -> SweepReport:
    if cancel is not None:
        cancel.check()

    def checked_progress(stage: str, done: int, total: int, detail: str) -> None:
        if cancel is not None:
            cancel.check()
        progress(stage, done, total, detail)

    return run_sweep(profile, session, http, firecrawl, limit=limit, progress=checked_progress)


def verify(
    session: Session,
    http: httpx.Client,
    profile: CandidateProfile,
    progress: ProgressFn = no_progress,
    cancel: CancelToken | None = None,
    delete_closed: bool = False,
) -> tuple[int, dict[str, int]]:
    if cancel is not None:
        cancel.check()

    def checked_progress(stage: str, done: int, total: int, detail: str) -> None:
        if cancel is not None:
            cancel.check()
        progress(stage, done, total, detail)

    pruned = prune_ineligible(session, profile)
    if cancel is not None:
        cancel.check()
    counts = verify_stored(session, http, checked_progress, delete_closed=delete_closed)
    return pruned, counts


def prune(session: Session, profile: CandidateProfile) -> int:
    """Deactivate stored jobs failing a profile gate or older than `job_max_age`."""
    return prune_ineligible(session, profile)


def prune_one(session: Session, job_id: str) -> JobPosting:
    """Manually remove one job; it stays hidden even if a later sweep finds it again."""
    row = repo.get_job(session, job_id)
    if row is None:
        raise ScoutError(f"Job not found: {job_id}")
    row.is_active = False
    row.status = JobStatus.PRUNED
    repo.record_audit(
        session,
        actor="human:user",
        action="JOB_EXCLUDED",
        status="SUCCESS",
        target_id=row.id,
        details={"reason": "manual: pruned by user", "title": row.title, "company": row.company},
    )
    session.commit()
    return row


def list_jobs(session: Session, min_score: int | None = None) -> list[JobPosting]:
    return repo.list_active(session, min_score=min_score)


def format_descriptions(session: Session) -> int:
    """Normalize and format unstructured job descriptions in the database."""
    count = 0
    for row in repo.list_active(session, active_only=False):
        formatted = format_unstructured_description(row.description)
        if formatted != row.description:
            row.description = formatted
            count += 1
    session.commit()
    return count


def verify_one(
    session: Session, http: httpx.Client, job_id: str, delete_closed: bool = False
) -> tuple[str, str]:
    row = repo.get_job(session, job_id)
    if row is None:
        raise ScoutError(f"Job not found: {job_id}")
    liveness = verifier_verify(row.url, http)
    target_id, target_url = row.id, row.url
    if liveness.status == "closed":
        if delete_closed:
            repo.delete_job(session, row.id)
        else:
            repo.mark_inactive(session, row.id)
    elif liveness.status == "live":
        row.last_verified_at = utcnow()
    repo.record_audit(
        session,
        actor="human:user",
        action="LINK_VERIFIED",
        status="SUCCESS" if liveness.status == "live" else "WARNING",
        target_id=target_id,
        details={"liveness": liveness.status, "reason": liveness.reason, "url": target_url},
    )
    session.commit()
    return liveness.status, liveness.reason

