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
from src.services.apply import ApplyError, apply_url, prepare
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
UNANSWERED = ["Why do you want to work at Hooli?", "I agree to the privacy policy"]


@pytest.fixture(scope="module")
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


def _job(
    session: Session, url: str, tmp_path: Path, tailored: bool = True, description: str = "Python"
) -> str:
    row = repo.upsert_job(
        session,
        RawJobPosting(
            "Senior Engineer", "Hooli", "San Francisco, CA", url, description, "greenhouse"
        ),
        JobScore(90, "tier1_primary_market", 5),
    )
    session.commit()
    if tailored:
        paths = artifact_paths(tmp_path, row.id)
        for path in (paths.resume, paths.cover_pdf, paths.cover_txt):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"%PDF-1.7")
    return row.id


def test_prepare_fills_form_and_escalates_unanswerable_questions(
    ats: MockATS, session: Session, profile: CandidateProfile, tmp_path: Path
) -> None:
    job_id = _job(session, ats.url("greenhouse_apply.html"), tmp_path)

    record = prepare(job_id, session=session, profile=profile, artifacts_dir=tmp_path)

    assert record.status == ApplicationStatus.NEEDS_INPUT and record.barrier is None
    assert [q["label"] for q in record.questions] == UNANSWERED
    assert record.questions[0]["kind"] == "textarea"
    planned = {p["label"]: (p["value"], p["source"]) for p in record.plan}
    assert planned["First Name"] == ("Jane", "profile")
    assert planned["Do you require sponsorship?"] == ("No", "screening")
    assert record.screenshot and Path(record.screenshot).read_bytes().startswith(b"\x89PNG")
    assert ats.submissions == []  # prepare never submits
    [event] = repo.query_audit(session, action="HITL_ESCALATED")
    assert event.target_id == job_id and event.details["status"] == "needs_input"


def test_prepare_with_candidate_answers_awaits_review(
    ats: MockATS, session: Session, profile: CandidateProfile, tmp_path: Path
) -> None:
    job_id = _job(session, ats.url("greenhouse_apply.html"), tmp_path)
    answers = {UNANSWERED[0]: "Your mission.", UNANSWERED[1]: "yes"}

    record = prepare(
        job_id, session=session, profile=profile, artifacts_dir=tmp_path, answers=answers
    )

    assert record.status == ApplicationStatus.AWAITING_REVIEW and record.questions == []
    assert record.answers == answers
    assert ats.submissions == []
    [event] = repo.query_audit(session, action="APPLICATION_PREPARED")
    assert event.details["fields_filled"] == len(record.plan)


def test_prepare_reuses_saved_answers(
    ats: MockATS, session: Session, profile: CandidateProfile, tmp_path: Path
) -> None:
    job_id = _job(session, ats.url("greenhouse_apply.html"), tmp_path)
    prepare(job_id, session=session, profile=profile, artifacts_dir=tmp_path)
    repo.save_application(
        session,
        job_id,
        status=ApplicationStatus.NEEDS_INPUT,
        answers={UNANSWERED[0]: "Mission.", UNANSWERED[1]: "yes"},
    )
    session.commit()
    assert (
        prepare(job_id, session=session, profile=profile, artifacts_dir=tmp_path).status
        == "awaiting_review"
    )


def test_login_wall_is_blocked_with_screenshot(
    ats: MockATS, session: Session, profile: CandidateProfile, tmp_path: Path
) -> None:
    job_id = _job(session, ats.url("login_wall.html"), tmp_path)
    record = prepare(job_id, session=session, profile=profile, artifacts_dir=tmp_path)
    assert (record.status, record.barrier) == ("blocked", "ACCOUNT_CREATION_REQUIRED")
    assert record.screenshot and Path(record.screenshot).exists()


@pytest.mark.parametrize(
    ("page", "error"),
    [("no_form.html", "No application form found"), ("missing.html", "HTTP 404")],
)
def test_pages_without_a_form_fail(
    ats: MockATS, session: Session, profile: CandidateProfile, tmp_path: Path, page: str, error: str
) -> None:
    job_id = _job(session, ats.url(page), tmp_path)
    record = prepare(job_id, session=session, profile=profile, artifacts_dir=tmp_path)
    assert record.status == ApplicationStatus.FAILED and error in (record.error or "")


def test_preconditions(
    ats: MockATS, session: Session, profile: CandidateProfile, tmp_path: Path
) -> None:
    with pytest.raises(ApplyError, match="No job"):
        prepare("job_00000000", session=session, profile=profile, artifacts_dir=tmp_path)
    untailored = _job(session, ats.url("greenhouse_apply.html") + "?u", tmp_path, tailored=False)
    with pytest.raises(ApplyError, match="job-butler tailor"):
        prepare(untailored, session=session, profile=profile, artifacts_dir=tmp_path)
    senior = _job(
        session,
        ats.url("greenhouse_apply.html") + "?s",
        tmp_path,
        description="20+ years of experience",
    )
    with pytest.raises(ApplyError, match="not eligible: experience"):
        prepare(senior, session=session, profile=profile, artifacts_dir=tmp_path)
    done = _job(session, ats.url("greenhouse_apply.html") + "?d", tmp_path)
    repo.save_application(session, done, status=ApplicationStatus.SUBMITTED)
    session.commit()
    with pytest.raises(ApplyError, match="already submitted"):
        prepare(done, session=session, profile=profile, artifacts_dir=tmp_path)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://jobs.lever.co/hooli/abc-123", "https://jobs.lever.co/hooli/abc-123/apply"),
        ("https://jobs.lever.co/hooli/abc-123/apply", "https://jobs.lever.co/hooli/abc-123/apply"),
        ("https://boards.greenhouse.io/hooli/jobs/1", "https://boards.greenhouse.io/hooli/jobs/1"),
    ],
)
def test_apply_url(url: str, expected: str) -> None:
    assert apply_url(url) == expected
