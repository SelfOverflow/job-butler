"""Tailor one stored job end to end: draft, fit, verify, ATS review, cover letter, save, audit."""

import time
from dataclasses import dataclass, replace
from pathlib import Path

from sqlalchemy.orm import Session

from src.agents.llm import LLMClient, LLMError
from src.agents.tailor.ats_review import AtsReview, review_resume
from src.agents.tailor.cover_letter import CoverLetterError, verified_facts, write_cover_letter
from src.agents.tailor.drafter import ReviewError, TailoredResume, draft_resume
from src.agents.tailor.pdf_verifier import PdfReport, extract_text, verify_pdf
from src.agents.tailor.summary import tailor_summary
from src.agents.tailor.typst_engine import FitError, fit_to_budget
from src.ingestion.base import ProgressFn, no_progress
from src.ingestion.scorer import score_job
from src.profile.models import CandidateProfile
from src.storage import repository as repo
from src.storage.models import JobPosting, JobStatus

ACTOR = "agent:tailor"
STEPS = 5


class TailorError(Exception):
    pass


@dataclass(frozen=True)
class ArtifactPaths:
    resume: Path
    cover_pdf: Path
    cover_txt: Path
    ats_report: Path


@dataclass(frozen=True)
class TailorResult:
    paths: ArtifactPaths
    selected: int  # Bullets chosen by the drafter (after review).
    kept: int  # Bullets that fit the page budget.
    roles: int
    pages: int
    report: PdfReport
    summary_tailored: bool = False  # False: the pre-written profile summary was used.
    ats: AtsReview | None = None  # None: the recruiter/ATS review was unavailable.
    ats_revised: bool = False  # True: one revision round improved on the first draft.


@dataclass(frozen=True)
class _Draft:
    resume: TailoredResume
    pdf: bytes
    kept: tuple[str, ...]
    report: PdfReport
    summary_tailored: bool


def artifact_paths(artifacts_dir: Path, job_id: str) -> ArtifactPaths:
    """Deterministic locations, so the dashboard can find files from the job id alone."""
    return ArtifactPaths(
        resume=artifacts_dir / "resumes" / f"{job_id}_resume.pdf",
        cover_pdf=artifacts_dir / "cover_letters" / f"{job_id}_cover.pdf",
        cover_txt=artifacts_dir / "cover_letters" / f"{job_id}_cover.txt",
        ats_report=artifacts_dir / "reports" / f"{job_id}_ats.json",
    )


def _draft(
    row: JobPosting,
    profile: CandidateProfile,
    llm: LLMClient,
    progress: ProgressFn,
    guidance: str | None = None,
) -> _Draft:
    resume = draft_resume(row, profile, llm, guidance)
    summary, summary_tailored = tailor_summary(row, profile, resume, llm, guidance)
    resume = replace(resume, summary=summary)
    progress("tailor", 2, STEPS, "Fitting Typst page budget...")
    pdf, kept = fit_to_budget(resume, profile)
    progress("tailor", 3, STEPS, "Verifying ATS text-layer & keywords...")
    report = verify_pdf(pdf, profile, resume.keywords, resume.pages)
    if not report.passed:
        raise TailorError(f"text-layer check failed: {'; '.join(report.problems)}")
    return _Draft(resume, pdf, kept, report, summary_tailored)


def _review(
    row: JobPosting, profile: CandidateProfile, draft: _Draft, llm: LLMClient
) -> AtsReview | None:
    facts = verified_facts(profile, draft.resume)
    return review_resume(row, extract_text(draft.pdf), facts, llm)


def _revise(
    row: JobPosting, profile: CandidateProfile, llm: LLMClient, draft: _Draft, ats: AtsReview
) -> tuple[_Draft, AtsReview] | None:
    """One revision for requirements the candidate has but the resume never states."""
    guidance = (
        "these job requirements are missing from the resume although the candidate's "
        f"verified facts show them: {', '.join(ats.missing_have_it)}. Prefer bullets and "
        "summary wording that evidence them, using the posting's exact terms."
    )
    try:
        retry = _draft(row, profile, llm, no_progress, guidance)
    except (LLMError, ReviewError, FitError, TailorError):
        return None
    retry_ats = _review(row, profile, retry, llm)
    if retry_ats is None or retry_ats.score < ats.score:
        return None
    return retry, retry_ats


def tailor_job(
    row: JobPosting,
    profile: CandidateProfile,
    llm: LLMClient,
    artifacts_dir: Path,
    session: Session,
    progress: ProgressFn = no_progress,
) -> TailorResult:
    started = time.monotonic()
    row.status = JobStatus.TAILORING
    session.commit()
    try:
        progress("tailor", 0, STEPS, "Starting resume tailoring...")
        if reason := score_job(repo.to_posting(row), profile).rejected_reason:
            raise TailorError(f"not eligible: {reason}")
        progress("tailor", 1, STEPS, "Drafting bullets & job-specific summary with LLM...")
        draft = _draft(row, profile, llm, progress)
        progress("tailor", 4, STEPS, "Recruiter ATS review...")
        ats, revised = _review(row, profile, draft, llm), False
        if ats is not None and ats.missing_have_it:
            progress("tailor", 4, STEPS, "Revising for requirements the resume missed...")
            if better := _revise(row, profile, llm, draft, ats):
                (draft, ats), revised = better, True
        progress("tailor", 5, STEPS, "Writing tailored cover letter...")
        letter = write_cover_letter(row, profile, draft.resume, llm)
    except (LLMError, ReviewError, FitError, CoverLetterError, TailorError) as exc:
        row.status = JobStatus.TAILOR_FAILED
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
    for path in (paths.resume, paths.cover_pdf, paths.ats_report):
        path.parent.mkdir(parents=True, exist_ok=True)
    paths.resume.write_bytes(draft.pdf)
    paths.cover_pdf.write_bytes(letter.pdf)
    paths.cover_txt.write_text(letter.text, encoding="utf-8")
    if ats is not None:
        paths.ats_report.write_text(ats.model_dump_json(indent=2), encoding="utf-8")
    else:
        paths.ats_report.unlink(missing_ok=True)  # Never show a stale review.

    resume, report = draft.resume, draft.report
    result = TailorResult(
        paths,
        len(resume.ranked_ids),
        len(draft.kept),
        len(resume.roles),
        report.pages,
        report,
        draft.summary_tailored,
        ats,
        revised,
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
            "summary": "tailored" if draft.summary_tailored else "profile",
            "keywords_matched": len(report.keywords_matched),
            "keywords_total": len(resume.keywords),
            "ats_score": ats.score if ats else None,
            "ats_verdict": ats.verdict if ats else "unavailable",
            "ats_missing": ats.missing_have_it if ats else [],
            "ats_gaps": ats.gaps if ats else [],
            "ats_revised": revised,
            "resume": str(paths.resume),
        },
    )
    row.status = JobStatus.TAILORED
    session.commit()
    return result
