"""Human-in-the-loop queue: review, answer, approve, skip, or resolve applications.

Thin layer over `src.services.apply` (shared with the CLI). Only `/approve` can
submit an application (AGENTS.md §5).
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from src.agents.navigator.browser import BrowserBusyError
from src.config.settings import Settings
from src.profile.loader import ProfileError, ProfileLoader
from src.profile.models import CandidateProfile
from src.server.deps import SessionDep, SettingsDep
from src.server.routes.jobs import JobId
from src.services import apply as service
from src.storage import repository as repo
from src.storage.models import PENDING_STATUSES, ApplicationRecord

router = APIRouter(prefix="/api/hitl")


class ApplicationOut(BaseModel):
    job_id: str
    title: str
    company: str
    url: str
    status: str
    barrier: str | None
    plan: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    answers: dict[str, str]
    error: str | None
    screenshot_url: str | None
    updated_at: datetime
    submitted_at: datetime | None


class AnswersIn(BaseModel):
    answers: dict[str, str]


def _out(record: ApplicationRecord) -> ApplicationOut:
    shot = record.screenshot and Path(record.screenshot).is_file()
    return ApplicationOut(
        job_id=record.job_id,
        title=record.job.title,
        company=record.job.company,
        url=record.job.url,
        status=record.status,
        barrier=record.barrier,
        plan=record.plan,
        questions=record.questions,
        answers=record.answers,
        error=record.error,
        screenshot_url=f"/api/hitl/{record.job_id}/screenshot" if shot else None,
        updated_at=record.updated_at,
        submitted_at=record.submitted_at,
    )


def _profile(settings: Settings) -> CandidateProfile:
    try:
        return ProfileLoader(settings.profile_path).load()
    except (ProfileError, ValidationError) as exc:
        raise HTTPException(422, f"Profile is invalid: {exc}") from None


def _require_job(session: Session, job_id: str) -> None:
    if repo.get_job(session, job_id) is None:
        raise HTTPException(404, f"No job with id {job_id}")


def _run(
    action: str, job_id: str, session: Session, settings: Settings, **kwargs: Any
) -> ApplicationOut:
    _require_job(session, job_id)
    try:
        if action == "skip":
            record = service.skip(job_id, session=session)
        elif action == "resolve":
            record = service.mark_applied(job_id, session=session)
        elif action == "approve":
            record = service.approve(
                job_id,
                session=session,
                profile=_profile(settings),
                artifacts_dir=settings.artifacts_dir,
            )
        else:
            record = service.prepare(
                job_id,
                session=session,
                profile=_profile(settings),
                artifacts_dir=settings.artifacts_dir,
                **kwargs,
            )
    except (service.ApplyError, BrowserBusyError) as exc:
        raise HTTPException(409, str(exc)) from None
    return _out(record)


@router.get("/pending", response_model=list[ApplicationOut])
def pending(session: SessionDep) -> list[ApplicationOut]:
    return [_out(r) for r in repo.list_applications(session, statuses=PENDING_STATUSES)]


@router.get("/applications", response_model=list[ApplicationOut])
def applications(session: SessionDep, status: str | None = None) -> list[ApplicationOut]:
    """All applications, optionally filtered by status (newest first)."""
    statuses = [status] if status else None
    return [_out(r) for r in repo.list_applications(session, statuses=statuses)]


@router.get("/{job_id}", response_model=ApplicationOut)
def get_application(job_id: JobId, session: SessionDep) -> ApplicationOut:
    """Retrieve application status and plan for a specific job."""
    _require_job(session, job_id)
    record = repo.get_application(session, job_id)
    if record is None:
        raise HTTPException(404, f"No application record for {job_id}")
    return _out(record)


@router.get("/{job_id}/screenshot")
def screenshot(job_id: JobId, session: SessionDep) -> FileResponse:
    record = repo.get_application(session, job_id)
    if record is None or not record.screenshot or not Path(record.screenshot).is_file():
        raise HTTPException(404, f"No screenshot for {job_id}")
    return FileResponse(record.screenshot, media_type="image/png")


@router.post("/{job_id}/prepare", response_model=ApplicationOut)
def prepare(job_id: JobId, session: SessionDep, settings: SettingsDep) -> ApplicationOut:
    """Fill the form for review. Never submits."""
    return _run("prepare", job_id, session, settings)


@router.post("/{job_id}/answers", response_model=ApplicationOut)
def answers(
    job_id: JobId, body: AnswersIn, session: SessionDep, settings: SettingsDep
) -> ApplicationOut:
    """Save the candidate's answers and re-prepare. Never submits."""
    saved = repo.get_application(session, job_id)
    merged = {**(saved.answers if saved else {}), **body.answers}
    return _run("prepare", job_id, session, settings, answers=merged)


@router.post("/{job_id}/approve", response_model=ApplicationOut)
def approve(job_id: JobId, session: SessionDep, settings: SettingsDep) -> ApplicationOut:
    """Submit the reviewed application: the only endpoint that submits."""
    return _run("approve", job_id, session, settings)


@router.post("/{job_id}/skip", response_model=ApplicationOut)
def skip(job_id: JobId, session: SessionDep, settings: SettingsDep) -> ApplicationOut:
    return _run("skip", job_id, session, settings)


@router.post("/{job_id}/resolve", response_model=ApplicationOut)
def resolve(job_id: JobId, session: SessionDep, settings: SettingsDep) -> ApplicationOut:
    """The candidate finished the application themselves."""
    return _run("resolve", job_id, session, settings)
