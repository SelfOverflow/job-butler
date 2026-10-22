"""Tailoring service shared by the CLI and web API (see slice 8)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from src.agents.llm import LLMClient
from src.agents.tailor.pdf_verifier import PdfReport, verify_pdf
from src.agents.tailor.runner import TailorError, TailorResult, tailor_job
from src.ingestion.base import ProgressFn, no_progress
from src.profile.models import CandidateProfile
from src.services.common import CancelToken
from src.storage import repository as repo
from src.storage.models import JobPosting


@dataclass
class TailoredItem:
    job: JobPosting
    result: TailorResult | None = None
    error: str | None = None


@dataclass
class TailorMatchesReport:
    total: int
    succeeded: int
    failed: int
    items: list[TailoredItem] = field(default_factory=list)


def tailor_one(
    job_id: str,
    *,
    profile: CandidateProfile,
    session: Session,
    llm: LLMClient,
    artifacts_dir: Path,
) -> tuple[JobPosting, TailorResult]:
    row = repo.get_job(session, job_id)
    if row is None:
        raise TailorError(f"No job with id {job_id}")
    result = tailor_job(row, profile, llm, artifacts_dir, session)
    return row, result


def tailor_matches(
    *,
    profile: CandidateProfile,
    session: Session,
    llm: LLMClient,
    artifacts_dir: Path,
    min_score: int = 75,
    progress: ProgressFn = no_progress,
    cancel: CancelToken | None = None,
) -> TailorMatchesReport:
    rows = repo.list_active(session, min_score=min_score)
    report = TailorMatchesReport(total=len(rows), succeeded=0, failed=0)
    progress("tailor", 0, len(rows), "")
    for done, row in enumerate(rows, start=1):
        if cancel is not None:
            cancel.check()
        try:
            result = tailor_job(row, profile, llm, artifacts_dir, session)
            report.succeeded += 1
            report.items.append(TailoredItem(job=row, result=result))
        except TailorError as exc:
            report.failed += 1
            report.items.append(TailoredItem(job=row, error=str(exc)))
        progress("tailor", done, len(rows), row.title)
    return report


def check_pdf(
    pdf_bytes: bytes,
    *,
    profile: CandidateProfile,
    keywords: Sequence[str] = (),
    max_pages: int | None = None,
) -> PdfReport:
    budget = max_pages or profile.preferences.cv_page_budget_rules.international
    return verify_pdf(pdf_bytes, profile, keywords=keywords, max_pages=budget)
