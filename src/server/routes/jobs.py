"""Job listing, detail, and tailored artifact downloads."""

from datetime import datetime, timedelta
from pathlib import Path as FilePath
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError

from src.agents.tailor.ats_review import AtsReview
from src.agents.tailor.runner import artifact_paths
from src.config.settings import Settings
from src.profile.loader import ProfileError, ProfileLoader
from src.server.deps import SessionDep, SettingsDep
from src.services import scout as scout_service
from src.storage import repository as repo
from src.storage.models import JobPosting, utcnow

router = APIRouter(prefix="/api")
ArtifactKind = Literal["resume", "cover_pdf", "cover_txt"]
JobId = Annotated[str, Path(pattern=r"^job_[0-9a-f]{8}$")]


class JobOut(BaseModel):
    id: str
    title: str
    company: str
    location: str
    url: str
    source: str
    score: int
    tier: str | None
    tier_label: str | None
    is_active: bool
    status: str
    posted_at: datetime | None
    discovered_at: datetime
    last_verified_at: datetime | None
    resume_url: str | None
    cover_letter_url: str | None
    cover_letter_txt_url: str | None


class JobDetail(JobOut):
    description: str
    ats_review: AtsReview | None = None  # Latest recruiter/ATS review, once tailored.


def _ats_review(settings: Settings, job_id: str) -> AtsReview | None:
    path = artifact_paths(settings.artifacts_dir, job_id).ats_report
    try:
        return AtsReview.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError):  # Missing or unreadable: show no review.
        return None


def _tier_labels(settings: Settings) -> dict[str, str]:
    try:
        hierarchy = ProfileLoader(settings.profile_path).load().preferences.sourcing_hierarchy
    except (ProfileError, ValidationError):
        return {}
    return {name: f"Tier {i}" for i, name in enumerate(hierarchy, start=1)}


def _out(row: JobPosting, settings: Settings, labels: dict[str, str]) -> dict[str, object]:
    paths = artifact_paths(settings.artifacts_dir, row.id)

    def url(kind: ArtifactKind, exists: bool) -> str | None:
        return f"/api/artifacts/{row.id}/{kind}" if exists else None

    return {
        **{c: getattr(row, c) for c in JobDetail.model_fields if hasattr(row, c)},
        "tier_label": labels.get(row.tier or ""),
        "resume_url": url("resume", paths.resume.is_file()),
        "cover_letter_url": url("cover_pdf", paths.cover_pdf.is_file()),
        "cover_letter_txt_url": url("cover_txt", paths.cover_txt.is_file()),
    }


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    session: SessionDep,
    settings: SettingsDep,
    min_score: int | None = None,
    include_inactive: bool = False,
    posted_within_hours: Annotated[int | None, Query(ge=1)] = None,
) -> list[dict[str, object]]:
    rows = repo.list_active(session, min_score=min_score, active_only=not include_inactive)
    if posted_within_hours is not None:  # Undated postings fall back to when we found them.
        cutoff = utcnow() - timedelta(hours=posted_within_hours)
        rows = [r for r in rows if (r.posted_at or r.discovered_at) >= cutoff]
    labels = _tier_labels(settings)
    return [_out(row, settings, labels) for row in rows]


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: JobId, session: SessionDep, settings: SettingsDep) -> dict[str, object]:
    row = repo.get_job(session, job_id)
    if row is None:
        raise HTTPException(404, f"No job with id {job_id}")
    return {
        **_out(row, settings, _tier_labels(settings)),
        "ats_review": _ats_review(settings, row.id),
    }


@router.post("/jobs/prune")
def prune_jobs(session: SessionDep, settings: SettingsDep) -> dict[str, int]:
    try:
        profile = ProfileLoader(settings.profile_path).load()
    except (ProfileError, ValidationError) as exc:
        raise HTTPException(422, f"Profile invalid: {exc}") from None
    return {"pruned": scout_service.prune(session, profile)}


@router.post("/jobs/{job_id}/prune")
def prune_job(job_id: JobId, session: SessionDep) -> dict[str, str]:
    try:
        row = scout_service.prune_one(session, job_id)
    except scout_service.ScoutError as exc:
        raise HTTPException(404, str(exc)) from None
    return {"job_id": row.id, "status": row.status}


@router.get("/artifacts/{job_id}/{kind}")
def download_artifact(job_id: JobId, kind: ArtifactKind, settings: SettingsDep) -> FileResponse:
    paths = artifact_paths(settings.artifacts_dir, job_id)
    path: FilePath = getattr(paths, kind)  # ArtifactKind values mirror ArtifactPaths fields.
    if not path.is_file():
        raise HTTPException(404, f"No {kind} for {job_id} yet; run `job-butler tailor`")
    media = "text/plain; charset=utf-8" if kind == "cover_txt" else "application/pdf"
    return FileResponse(
        path, media_type=media, filename=path.name, content_disposition_type="inline"
    )
