"""Application service shared by the CLI and the web API (see slice 8).

Review-first policy (AGENTS.md §5): `prepare` fills the form and stores the answer
plan, but never submits. Submission happens only in `approve`, after the candidate
explicitly approves.
"""

import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from sqlalchemy.orm import Session

from src.agents.navigator.barrier_detector import detect_barrier
from src.agents.navigator.browser import browser_page
from src.agents.navigator.field_mapper import FillPlan, map_fields
from src.agents.navigator.form_inspector import fill_form, inspect_form, submit_form
from src.agents.tailor.runner import ArtifactPaths, artifact_paths
from src.ingestion.base import html_to_text
from src.ingestion.scorer import score_job
from src.profile.models import CandidateProfile
from src.storage import repository as repo
from src.storage.models import ApplicationRecord, ApplicationStatus, JobPosting, utcnow

ACTOR = "agent:navigator"
_CONFIRMED = re.compile(
    r"thank you for (?:applying|your application)|application (?:has been )?(?:received|submitted)|"
    r"we(?:'ve| have) received your application|successfully submitted",
    re.IGNORECASE,
)
CHANGED = "The form changed since you reviewed it; please review again."
OpenPage = Callable[[], AbstractContextManager[Page]]


class ApplyError(Exception):
    pass


def apply_url(url: str) -> str:
    """Lever postings take applications at <posting>/apply; others on the posting page."""
    if urlsplit(url).hostname == "jobs.lever.co" and not url.rstrip("/").endswith("/apply"):
        return url.rstrip("/") + "/apply"
    return url


def _eligible_job(
    session: Session, job_id: str, profile: CandidateProfile, artifacts_dir: Path
) -> tuple[JobPosting, ArtifactPaths]:
    row = repo.get_job(session, job_id)
    if row is None:
        raise ApplyError(f"No job with id {job_id}")
    if reason := score_job(repo.to_posting(row), profile).rejected_reason:
        raise ApplyError(f"not eligible: {reason}")
    paths = artifact_paths(artifacts_dir, row.id)
    if not paths.resume.is_file():
        raise ApplyError(f"Not tailored yet: run `job-butler tailor --job-id {row.id}` first")
    record = repo.get_application(session, row.id)
    if record and record.status in (
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.APPLIED_MANUALLY,
    ):
        raise ApplyError(f"Application already {record.status.replace('_', ' ')}")
    return row, paths


def _serialize(plan: FillPlan) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # Same shape as after a JSON round-trip (lists, not tuples) so plans compare exactly.
    planned = [
        {
            **asdict(p.field),
            "options": list(p.field.options),
            "option_values": list(p.field.option_values),
            "value": p.value,
            "source": p.source,
        }
        for p in plan.planned
    ]
    questions = [
        {"label": f.label, "kind": f.kind, "options": [o for o in f.options if o.strip()]}
        for f in plan.unanswered
    ]
    return planned, questions


def _record(
    session: Session,
    job_id: str,
    status: ApplicationStatus,
    action: str = "APPLICATION_PREPARED",
    **fields: Any,
) -> ApplicationRecord:
    record = repo.save_application(session, job_id, status=status, **fields)
    escalated = status in (ApplicationStatus.BLOCKED, ApplicationStatus.NEEDS_INPUT)
    repo.record_audit(
        session,
        actor=ACTOR,
        action="HITL_ESCALATED" if escalated else action,
        status="WARNING" if escalated else "FAILURE" if status == "failed" else "SUCCESS",
        target_id=job_id,
        details={
            "status": status.value,
            "barrier": record.barrier,
            "questions": [q["label"] for q in record.questions],
            "fields_filled": len(record.plan),
            "error": record.error,
        },
    )
    session.commit()
    return record


def prepare(
    job_id: str,
    *,
    session: Session,
    profile: CandidateProfile,
    artifacts_dir: Path,
    answers: dict[str, str] | None = None,
    open_page: OpenPage = browser_page,
) -> ApplicationRecord:
    """Open the form, detect barriers, fill verified answers, screenshot. Never submits."""
    row, paths = _eligible_job(session, job_id, profile, artifacts_dir)
    existing = repo.get_application(session, row.id)
    answers = answers if answers is not None else (existing.answers if existing else {})
    shot = artifacts_dir / "applications" / f"{row.id}_prepared.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    common: dict[str, Any] = {"answers": answers, "screenshot": None, "error": None}

    try:
        with open_page() as page:
            response = page.goto(apply_url(row.url), wait_until="domcontentloaded")
            if response is not None and response.status >= 400:
                raise ApplyError(f"HTTP {response.status} at {page.url}")
            if barrier := detect_barrier(page.url, page.content()):
                page.screenshot(path=shot, full_page=True)
                blocked = {**common, "screenshot": str(shot), "plan": [], "questions": []}
                return _record(
                    session, row.id, ApplicationStatus.BLOCKED, barrier=barrier.value, **blocked
                )
            fields = inspect_form(page)
            if not fields:
                raise ApplyError("No application form found on the page")
            plan = map_fields(fields, profile, paths, answers)
            fill_form(page, plan)
            page.screenshot(path=shot, full_page=True)
    except (ApplyError, PlaywrightError) as exc:
        return _record(session, row.id, ApplicationStatus.FAILED, **{**common, "error": str(exc)})

    planned, questions = _serialize(plan)
    status = ApplicationStatus.NEEDS_INPUT if questions else ApplicationStatus.AWAITING_REVIEW
    filled = {**common, "screenshot": str(shot), "plan": planned, "questions": questions}
    return _record(session, row.id, status, barrier=None, **filled)


def approve(
    job_id: str,
    *,
    session: Session,
    profile: CandidateProfile,
    artifacts_dir: Path,
    open_page: OpenPage = browser_page,
) -> ApplicationRecord:
    """Submit the reviewed application. The only code path that ever clicks Submit."""
    record = repo.get_application(session, job_id)
    if record is None:
        raise ApplyError(f"No prepared application for {job_id}; prepare it first")
    if record.status in (ApplicationStatus.SUBMITTED, ApplicationStatus.APPLIED_MANUALLY):
        raise ApplyError(f"Application already {record.status.replace('_', ' ')}")
    if record.status != ApplicationStatus.AWAITING_REVIEW:
        raise ApplyError(f"Cannot approve: application {record.status.replace('_', ' ')}")
    row, paths = _eligible_job(session, job_id, profile, artifacts_dir)
    shot = artifacts_dir / "applications" / f"{row.id}_submitted.png"
    shot.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open_page() as page:
            response = page.goto(apply_url(row.url), wait_until="domcontentloaded")
            if response is not None and response.status >= 400:
                raise ApplyError(f"HTTP {response.status} at {page.url}")
            if barrier := detect_barrier(page.url, page.content()):
                return _record(session, row.id, ApplicationStatus.BLOCKED, barrier=barrier.value)
            plan = map_fields(inspect_form(page), profile, paths, record.answers)
            planned, questions = _serialize(plan)
            if questions or planned != record.plan:  # Only ever submit what was reviewed.
                status = (
                    ApplicationStatus.NEEDS_INPUT
                    if questions
                    else ApplicationStatus.AWAITING_REVIEW
                )
                return _record(
                    session, row.id, status, plan=planned, questions=questions, error=CHANGED
                )
            fill_form(page, plan)
            submit_form(page, plan)
            page.screenshot(path=shot, full_page=True)
            confirmed = bool(_CONFIRMED.search(html_to_text(page.content())))
    except (ApplyError, PlaywrightError) as exc:
        return _record(session, row.id, ApplicationStatus.FAILED, "FORM_SUBMITTED", error=str(exc))

    if not confirmed:
        error = "Submission not confirmed: check the portal manually before retrying"
        return _record(
            session,
            row.id,
            ApplicationStatus.FAILED,
            "FORM_SUBMITTED",
            screenshot=str(shot),
            error=error,
        )
    return _record(
        session,
        row.id,
        ApplicationStatus.SUBMITTED,
        "FORM_SUBMITTED",
        screenshot=str(shot),
        error=None,
        submitted_at=utcnow(),
    )


def _decide(
    session: Session, job_id: str, status: ApplicationStatus, action: str
) -> ApplicationRecord:
    if repo.get_job(session, job_id) is None:
        raise ApplyError(f"No job with id {job_id}")
    extra = {"submitted_at": utcnow()} if status == ApplicationStatus.APPLIED_MANUALLY else {}
    record = repo.save_application(session, job_id, status=status, **extra)
    repo.record_audit(
        session, actor="human:user", action=action, status="SUCCESS", target_id=job_id
    )
    session.commit()
    return record


def skip(job_id: str, *, session: Session) -> ApplicationRecord:
    return _decide(session, job_id, ApplicationStatus.SKIPPED, "APPLICATION_SKIPPED")


def mark_applied(job_id: str, *, session: Session) -> ApplicationRecord:
    """The candidate applied themselves (e.g. after creating a portal account)."""
    return _decide(
        session, job_id, ApplicationStatus.APPLIED_MANUALLY, "APPLICATION_MARKED_APPLIED"
    )
