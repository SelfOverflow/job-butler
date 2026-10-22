"""Scout sweep: discover -> exclude -> dedupe -> score -> verify -> persist (+ audit)."""

import time
from dataclasses import asdict, dataclass, field

import httpx
from sqlalchemy.orm import Session

from src.ingestion.deduplicator import dedupe
from src.ingestion.discovery import discover
from src.ingestion.filter import drop_excluded
from src.ingestion.firecrawl_client import FirecrawlClient
from src.ingestion.scorer import score_job
from src.ingestion.verifier import verify
from src.profile.models import CandidateProfile
from src.storage import repository as repo
from src.storage.models import utcnow

ACTOR = "agent:scout"


@dataclass
class SweepReport:
    discovered: int = 0
    excluded: int = 0
    duplicates: int = 0
    rejected: int = 0  # Failed the visa gate.
    closed: int = 0  # Dead links found during verification.
    saved: int = 0
    new: int = 0
    errors: list[str] = field(default_factory=list)


def run_sweep(
    profile: CandidateProfile,
    session: Session,
    http: httpx.Client,
    firecrawl: FirecrawlClient | None,
    limit: int | None = None,
) -> SweepReport:
    """One full scout cycle. Only the top `limit` jobs by score are verified and saved."""
    started = time.monotonic()
    report = SweepReport()
    jobs, report.errors = discover(profile, firecrawl, http)
    report.discovered = len(jobs)

    kept = drop_excluded(jobs, profile.preferences.excluded_employers)
    report.excluded = len(jobs) - len(kept)
    unique = dedupe(kept)
    report.duplicates = len(kept) - len(unique)

    scored = [(job, score_job(job, profile)) for job in unique]
    eligible = [(job, s) for job, s in scored if s.rejected_reason is None]
    report.rejected = len(scored) - len(eligible)
    eligible.sort(key=lambda pair: pair[1].score, reverse=True)

    for job, score in eligible[:limit]:
        liveness = verify(job.url, http)
        if liveness.status == "closed":
            report.closed += 1
            continue
        is_new = repo.get_job(session, repo.job_id(job)) is None
        row = repo.upsert_job(session, job, score)
        if liveness.status == "live":
            row.last_verified_at = utcnow()
        report.saved += 1
        if is_new:
            report.new += 1
            repo.record_audit(
                session,
                actor=ACTOR,
                action="JOB_DISCOVERED",
                status="SUCCESS",
                target_id=row.id,
                details={"score": score.score, "tier": score.tier, "source": job.source},
            )

    repo.record_audit(
        session,
        actor=ACTOR,
        action="SCOUT_SWEEP",
        status="WARNING" if report.errors else "SUCCESS",
        duration_ms=round((time.monotonic() - started) * 1000),
        details=asdict(report),
    )
    session.commit()
    return report


def verify_stored(session: Session, http: httpx.Client) -> dict[str, int]:
    """Re-check every active job; closed ones are deactivated, unknown ones kept."""
    counts = {"live": 0, "closed": 0, "unknown": 0}
    for row in repo.list_active(session):
        liveness = verify(row.url, http)
        counts[liveness.status] += 1
        if liveness.status == "closed":
            repo.mark_inactive(session, row.id)
        elif liveness.status == "live":
            row.last_verified_at = utcnow()
        repo.record_audit(
            session,
            actor=ACTOR,
            action="LINK_VERIFIED",
            status="SUCCESS" if liveness.status == "live" else "WARNING",
            target_id=row.id,
            details={"liveness": liveness.status, "reason": liveness.reason, "url": row.url},
        )
    session.commit()
    return counts
