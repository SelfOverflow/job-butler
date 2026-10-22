"""Tailor one stored job end to end: draft, fit, verify, cover letter, save, audit."""

import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from src.agents.llm import LLMClient, LLMError
from src.agents.tailor.cover_letter import CoverLetterError, write_cover_letter
from src.agents.tailor.drafter import ReviewError, draft_resume
from src.agents.tailor.pdf_verifier import PdfReport, verify_pdf
from src.agents.tailor.typst_engine import FitError, fit_to_budget
from src.profile.models import CandidateProfile
from src.storage import repository as repo
from src.storage.models import JobPosting

ACTOR = "agent:tailor"


class TailorError(Exception):
    pass


@dataclass(frozen=True)
class ArtifactPaths:
    resume: Path
    cover_pdf: Path
    cover_txt: Path


@dataclass(frozen=True)
class TailorResult:
    paths: ArtifactPaths
    selected: int  # Bullets chosen by the drafter (after review).
    kept: int  # Bullets that fit the page budget.
    roles: int
    pages: int
    report: PdfReport


def artifact_paths(artifacts_dir: Path, job_id: str) -> ArtifactPaths:
    """Deterministic locations, so the dashboard can find files from the job id alone."""
    return ArtifactPaths(
        resume=artifacts_dir / "resumes" / f"{job_id}_resume.pdf",
        cover_pdf=artifacts_dir / "cover_letters" / f"{job_id}_cover.pdf",
        cover_txt=artifacts_dir / "cover_letters" / f"{job_id}_cover.txt",
    )


def tailor_job(
    row: JobPosting,
    profile: CandidateProfile,
    llm: LLMClient,
    artifacts_dir: Path,
    session: Session,
) -> TailorResult:
    started = time.monotonic()
    try:
        resume = draft_resume(row, profile, llm)
        pdf, kept = fit_to_budget(resume, profile)
        report = verify_pdf(pdf, profile, resume.keywords, resume.pages)
        if not report.passed:
            raise TailorError(f"text-layer check failed: {'; '.join(report.problems)}")
        letter = write_cover_letter(row, profile, resume, llm)
    except (LLMError, ReviewError, FitError, CoverLetterError, TailorError) as exc:
        repo.record_audit(
            session,
            actor=ACTOR,
            action="RESUME_TAILORED",
            status="FAILURE",
            target_id=row.id,
            duration_ms=round((time.monotonic() - started) * 1000),
            details={"error": str(exc)},
        )
        session.commit()
        raise TailorError(str(exc)) from exc

    paths = artifact_paths(artifacts_dir, row.id)
    for path in (paths.resume, paths.cover_pdf):
        path.parent.mkdir(parents=True, exist_ok=True)
    paths.resume.write_bytes(pdf)
    paths.cover_pdf.write_bytes(letter.pdf)
    paths.cover_txt.write_text(letter.text, encoding="utf-8")

    result = TailorResult(
        paths, len(resume.ranked_ids), len(kept), len(resume.roles), report.pages, report
    )
    repo.record_audit(
        session,
        actor=ACTOR,
        action="RESUME_TAILORED",
        status="SUCCESS",
        target_id=row.id,
        duration_ms=round((time.monotonic() - started) * 1000),
        details={
            "pages": report.pages,
            "page_budget": resume.pages,
            "bullets_selected": result.selected,
            "bullets_kept": result.kept,
            "keywords_matched": len(report.keywords_matched),
            "keywords_total": len(resume.keywords),
            "resume": str(paths.resume),
        },
    )
    session.commit()
    return result
