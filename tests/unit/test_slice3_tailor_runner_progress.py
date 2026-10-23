from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.agents.tailor.ats_review import AtsReview
from src.agents.tailor.cover_letter import CoverLetterDraft
from src.agents.tailor.drafter import DraftPlan
from src.agents.tailor.runner import TailorError, tailor_job
from src.agents.tailor.summary import SummaryDraft
from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.profile.loader import ProfileLoader
from src.profile.models import CandidateProfile
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory
from src.storage.models import JobPosting, JobStatus
from tests.fakes import FakeLLM, ats_review, template_summary

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
JD = "Python, FastAPI, Kafka and PostgreSQL."


def _llm(bullet_ids: list[str]) -> FakeLLM:
    def respond(prompt: str, schema: type[BaseModel]) -> BaseModel:
        if schema is SummaryDraft:
            return template_summary()
        if schema is AtsReview:
            return ats_review()
        if schema is CoverLetterDraft:
            return CoverLetterDraft(greeting="Hi,", paragraphs=["Keen."], closing="Best,")
        return DraftPlan(keywords=["Python", "Kafka"], bullet_ids=bullet_ids)

    return FakeLLM(respond)


@pytest.fixture
def profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CandidateProfile:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    path = tmp_path / "profile.yaml"
    path.write_text(TEMPLATE.read_text())
    return ProfileLoader(path).load()


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    with session_factory(engine)() as s:
        yield s
    engine.dispose()


def _row(session: Session) -> JobPosting:
    job = RawJobPosting(
        "Senior Backend Engineer", "Hooli", "San Francisco, CA", "https://x/1", JD, "greenhouse"
    )
    row = repo.upsert_job(session, job, JobScore(94, "tier1_primary_market", 5))
    session.commit()
    return row


def test_tailor_job_reports_four_stages_and_marks_tailored(
    profile: CandidateProfile, session: Session, tmp_path: Path
) -> None:
    row = _row(session)
    calls: list[tuple[str, int, int, str, str]] = []

    def progress(stage: str, done: int, total: int, detail: str) -> None:
        calls.append((stage, done, total, detail, row.status))

    tailor_job(row, profile, _llm(["b_alpha_1", "b_beta_1"]), tmp_path / "a", session, progress)

    assert [(c[0], c[1], c[2]) for c in calls] == [("tailor", i, 5) for i in range(6)]
    assert all(c[4] == JobStatus.TAILORING for c in calls)
    assert "Drafting" in calls[1][3] and "page budget" in calls[2][3]
    assert "text-layer" in calls[3][3] and "Recruiter ATS review" in calls[4][3]
    assert "cover letter" in calls[5][3]
    session.expire_all()
    assert row.status == JobStatus.TAILORED


def test_tailor_job_failure_marks_tailor_failed(
    profile: CandidateProfile, session: Session, tmp_path: Path
) -> None:
    row = _row(session)
    with pytest.raises(TailorError):
        tailor_job(row, profile, _llm(["b_invented"]), tmp_path / "a", session)
    session.expire_all()
    assert row.status == JobStatus.TAILOR_FAILED
