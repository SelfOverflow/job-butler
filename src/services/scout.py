"""Scout service shared by the CLI and web API (see slice 8)."""

import httpx
from sqlalchemy.orm import Session

from src.ingestion.base import ProgressFn, no_progress
from src.ingestion.firecrawl_client import FirecrawlClient
from src.ingestion.pipeline import SweepReport, prune_ineligible, run_sweep, verify_stored
from src.profile.models import CandidateProfile
from src.services.common import CancelToken
from src.storage import repository as repo
from src.storage.models import JobPosting


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
    counts = verify_stored(session, http, checked_progress)
    return pruned, counts


def list_jobs(session: Session, min_score: int | None = None) -> list[JobPosting]:
    return repo.list_active(session, min_score=min_score)
