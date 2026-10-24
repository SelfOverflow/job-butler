"""Scout sweep: discover -> exclude -> dedupe -> score -> verify -> persist (+ audit)."""

import time
from dataclasses import asdict, dataclass, field

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.analytics.market import analyze
from src.ingestion.base import ProgressFn, RawJobPosting, contains_phrase, no_progress, words
from src.ingestion.deduplicator import dedupe
from src.ingestion.discovery import discover
from src.ingestion.filter import drop_excluded
from src.ingestion.firecrawl_client import FirecrawlClient
from src.ingestion.recency import is_recent
from src.ingestion.scorer import JobScore, score_job
from src.ingestion.verifier import verify
from src.profile.models import CandidateProfile
from src.storage import repository as repo
from src.storage.models import JobPosting, JobStatus, utcnow

ACTOR = "agent:scout"


@dataclass
class SweepReport:
    discovered: int = 0
    excluded: int = 0
    duplicates: int = 0
    stale: int = 0  # Published before the profile's job_recency window.
    rejected: int = 0  # Failed a hard gate (experience, visa); see rejected_by.
    rejected_by: dict[str, int] = field(default_factory=dict)
    pruned: int = 0  # Stored jobs deactivated because they no longer fit the profile.
    market_postings: int = 0  # Gate-passing postings in this sweep's market snapshot.
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
    progress: ProgressFn = no_progress,
) -> SweepReport:
    """One full scout cycle. Only the top `limit` jobs by score are verified and saved."""
    started = time.monotonic()
    report = SweepReport(pruned=prune_ineligible(session, profile))
    jobs, report.errors = discover(profile, firecrawl, http, progress)
    report.discovered = len(jobs)

    kept = drop_excluded(jobs, profile.preferences.excluded_employers)
    report.excluded = len(jobs) - len(kept)
    unique = dedupe(kept)
    report.duplicates = len(kept) - len(unique)
    prefs = profile.preferences
    fresh = [
        j
        for j in unique
        if is_recent(j.posted_at, prefs.job_recency) and is_recent(j.posted_at, prefs.job_max_age)
    ]
    report.stale = len(unique) - len(fresh)
    market = analyze(fresh, profile)  # Whole eligible market, not just the saved top N.
    if market.total:
        repo.save_market_snapshot(session, market)
        session.commit()
    report.market_postings = market.total

    scored = [(job, score_job(job, profile)) for job in fresh]
    eligible = [(job, s) for job, s in scored if s.rejected_reason is None]
    report.rejected = len(scored) - len(eligible)
    for _, s in scored:
        if s.rejected_reason:
            gate = s.rejected_reason.split(":")[0]
            report.rejected_by[gate] = report.rejected_by.get(gate, 0) + 1
    eligible = prioritise(eligible, profile)

    to_verify = eligible[:limit]
    progress("verify", 0, len(to_verify), "")
    for done, (job, score) in enumerate(to_verify, start=1):
        liveness = verify(job.url, http)
        progress("verify", done, len(to_verify), job.url)
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
        session.commit()

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


def prioritise(
    scored: list[tuple[RawJobPosting, JobScore]], profile: CandidateProfile
) -> list[tuple[RawJobPosting, JobScore]]:
    """Jobs from the candidate's watched career portals first, then by fit score."""
    watched = [words(c.name) for c in profile.preferences.watched_companies]

    def is_watched(job: RawJobPosting) -> bool:
        return any(contains_phrase(words(job.company), name) for name in watched)

    return sorted(scored, key=lambda pair: (is_watched(pair[0]), pair[1].score), reverse=True)


def prune_ineligible(session: Session, profile: CandidateProfile) -> int:
    """Re-score stored jobs against the current profile; deactivate those failing a gate
    or older than `preferences.job_max_age`.

    Kept jobs get fresh score/tier/boost, so profile edits (tiers, skills, experience)
    take effect without waiting for the job to be rediscovered.
    """
    pruned = 0
    max_age = profile.preferences.job_max_age
    for row in repo.list_active(session):
        result = score_job(repo.to_posting(row), profile)
        reason = result.rejected_reason
        if not reason and not is_recent(row.posted_at or row.discovered_at, max_age):
            reason = f"stale: older than {max_age}"
        if not reason:
            row.score, row.tier, row.boost = result.score, result.tier, result.boost
        else:
            repo.mark_inactive(session, row.id)
            repo.record_audit(
                session,
                actor=ACTOR,
                action="JOB_EXCLUDED",
                status="WARNING",
                target_id=row.id,
                details={"reason": reason, "title": row.title, "company": row.company},
            )
            pruned += 1
    session.commit()
    return pruned


def verify_stored(
    session: Session,
    http: httpx.Client,
    progress: ProgressFn = no_progress,
    delete_closed: bool = False,
) -> dict[str, int]:
    """Re-check every active job; closed ones are deactivated (or deleted), unknown ones kept."""
    counts = {"live": 0, "closed": 0, "unknown": 0}
    if delete_closed:
        counts["deleted"] = 0
        inactive_rows = list(
            session.scalars(
                select(JobPosting).where(
                    JobPosting.is_active == False,  # noqa: E712
                    JobPosting.status != JobStatus.PRUNED,
                )
            )
        )
        for inact in inactive_rows:
            repo.delete_job(session, inact.id)
            counts["deleted"] += 1

    rows = repo.list_active(session)
    progress("verify", 0, len(rows), "")
    for done, row in enumerate(rows, start=1):
        liveness = verify(row.url, http)
        progress("verify", done, len(rows), row.url)
        counts[liveness.status] += 1
        target_id, target_url = row.id, row.url
        if liveness.status == "closed":
            if delete_closed:
                repo.delete_job(session, row.id)
                counts["deleted"] += 1
            else:
                repo.mark_inactive(session, row.id)
        elif liveness.status == "live":
            row.last_verified_at = utcnow()
        repo.record_audit(
            session,
            actor=ACTOR,
            action="LINK_VERIFIED",
            status="SUCCESS" if liveness.status == "live" else "WARNING",
            target_id=target_id,
            details={"liveness": liveness.status, "reason": liveness.reason, "url": target_url},
        )
        session.commit()
    session.commit()
    return counts
