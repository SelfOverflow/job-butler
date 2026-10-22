from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy.orm import Session

from src.agents.tailor.runner import artifact_paths
from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile
from src.services.apply import ApplyError, approve, mark_applied, prepare, skip
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory
from src.storage.models import ApplicationStatus
from tests.mock_ats import MockATS, mock_ats

ROOT = Path(__file__).resolve().parents[2]
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
ANSWERS = {
    "Why do you want to work at Hooli?": "Your mission.",
    "I agree to the privacy policy": "yes",
}


@pytest.fixture
def ats() -> Iterator[MockATS]:
    with mock_ats() as server:
        yield server


@pytest.fixture
def profile() -> CandidateProfile:
    raw: dict[str, Any] = interpolate(
        yaml.safe_load((ROOT / "profile" / "candidate_profile.template.yaml").read_text()), ENV
    )
    return CandidateProfile.model_validate(raw)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    with session_factory(engine)() as s:
        yield s
    engine.dispose()


def _prepared(
    session: Session, profile: CandidateProfile, tmp_path: Path, url: str, answers: dict[str, str]
) -> str:
    job = RawJobPosting(
        "Senior Engineer", "Hooli", "San Francisco, CA", url, "Python", "greenhouse"
    )
    row = repo.upsert_job(session, job, JobScore(90, "tier1_primary_market", 5))
    session.commit()
    paths = artifact_paths(tmp_path, row.id)
    for path in (paths.resume, paths.cover_pdf, paths.cover_txt):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.7")
    prepare(row.id, session=session, profile=profile, artifacts_dir=tmp_path, answers=answers)
    return row.id


def test_approve_submits_the_reviewed_plan(
    ats: MockATS, session: Session, profile: CandidateProfile, tmp_path: Path
) -> None:
    job_id = _prepared(session, profile, tmp_path, ats.url("greenhouse_apply.html"), ANSWERS)
    assert ats.submissions == []

    record = approve(job_id, session=session, profile=profile, artifacts_dir=tmp_path)

    assert record.status == ApplicationStatus.SUBMITTED and record.submitted_at is not None
    [body] = ats.submissions
    assert b"Jane" in body and b"Your mission." in body and b"job_" in body  # resume file name
    assert (
        record.screenshot
        and record.screenshot.endswith("_submitted.png")
        and Path(record.screenshot).exists()
    )
    [event] = repo.query_audit(session, action="FORM_SUBMITTED")
    assert (event.status, event.target_id) == ("SUCCESS", job_id)

    with pytest.raises(ApplyError, match="already submitted"):
        approve(job_id, session=session, profile=profile, artifacts_dir=tmp_path)
    assert len(ats.submissions) == 1  # never twice


def test_approve_refuses_unless_awaiting_review(
    ats: MockATS, session: Session, profile: CandidateProfile, tmp_path: Path
) -> None:
    job_id = _prepared(
        session, profile, tmp_path, ats.url("greenhouse_apply.html"), {}
    )  # needs_input
    with pytest.raises(ApplyError, match="needs input"):
        approve(job_id, session=session, profile=profile, artifacts_dir=tmp_path)
    with pytest.raises(ApplyError, match="no prepared application"):
        approve("job_00000000", session=session, profile=profile, artifacts_dir=tmp_path)
    assert ats.submissions == []


def test_changed_form_returns_to_review_without_submitting(
    ats: MockATS, session: Session, profile: CandidateProfile, tmp_path: Path
) -> None:
    job_id = _prepared(session, profile, tmp_path, ats.url("greenhouse_apply.html"), ANSWERS)
    record = repo.get_application(session, job_id)
    assert record is not None
    reviewed = [dict(p) for p in record.plan]
    reviewed[0]["value"] = (
        "Someone Else"  # what the candidate reviewed differs from the live mapping
    )
    repo.save_application(session, job_id, status=ApplicationStatus.AWAITING_REVIEW, plan=reviewed)
    session.commit()

    record = approve(job_id, session=session, profile=profile, artifacts_dir=tmp_path)

    assert record.status == ApplicationStatus.AWAITING_REVIEW
    assert "changed since you reviewed" in (record.error or "")
    assert record.plan[0]["value"] == "Jane"  # refreshed plan for re-review
    assert ats.submissions == []


def test_unconfirmed_submission_fails_without_retry(
    ats: MockATS, session: Session, profile: CandidateProfile, tmp_path: Path
) -> None:
    job_id = _prepared(session, profile, tmp_path, ats.url("greenhouse_reject.html"), ANSWERS)
    record = approve(job_id, session=session, profile=profile, artifacts_dir=tmp_path)
    assert record.status == ApplicationStatus.FAILED
    assert "not confirmed" in (record.error or "") and len(ats.submissions) == 1


def test_skip_and_mark_applied(
    ats: MockATS, session: Session, profile: CandidateProfile, tmp_path: Path
) -> None:
    job_id = _prepared(session, profile, tmp_path, ats.url("login_wall.html"), {})
    assert skip(job_id, session=session).status == ApplicationStatus.SKIPPED
    assert mark_applied(job_id, session=session).status == ApplicationStatus.APPLIED_MANUALLY
    actions = [e.action for e in repo.query_audit(session, actor="human:user")]
    assert actions == ["APPLICATION_MARKED_APPLIED", "APPLICATION_SKIPPED"]
    with pytest.raises(ApplyError):
        skip("job_00000000", session=session)
