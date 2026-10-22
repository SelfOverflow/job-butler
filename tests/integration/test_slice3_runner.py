from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.agents.tailor.cover_letter import CoverLetterDraft
from src.agents.tailor.drafter import DraftPlan
from src.agents.tailor.pdf_verifier import PdfReport
from src.agents.tailor.runner import TailorError, artifact_paths, tailor_job
from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory
from src.storage.models import JobPosting
from tests.fakes import FakeLLM

ROOT = Path(__file__).resolve().parents[2]
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
JOB = RawJobPosting(
    "Senior Backend Engineer", "Hooli", "San Francisco, CA", "https://jobs.example/1",
    "Python, FastAPI, Kafka and PostgreSQL at scale.", "greenhouse",
)  # fmt: skip
LETTER = CoverLetterDraft(
    greeting="Dear Hooli Hiring Team,",
    paragraphs=["I am applying for the Senior Backend Engineer role.", "I build reliable systems."],
    closing="Sincerely,",
)


def llm_for(plan: DraftPlan) -> FakeLLM:
    def respond(_prompt: str, schema: type[BaseModel]) -> BaseModel:
        return plan if schema is DraftPlan else LETTER

    return FakeLLM(respond)


GOOD_PLAN = DraftPlan(
    keywords=["Python", "Kafka", "PostgreSQL"], bullet_ids=["b_alpha_1", "b_beta_1"]
)


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


@pytest.fixture
def row(session: Session) -> JobPosting:
    job = repo.upsert_job(session, JOB, JobScore(94, "tier1_primary_market", 5))
    session.commit()
    return job


def test_tailor_job_writes_verified_artifacts_and_audits(
    profile: CandidateProfile, session: Session, row: JobPosting, tmp_path: Path
) -> None:
    result = tailor_job(row, profile, llm_for(GOOD_PLAN), tmp_path / "artifacts", session)

    paths = artifact_paths(tmp_path / "artifacts", row.id)
    assert result.paths == paths
    assert paths.resume.read_bytes().startswith(b"%PDF-")
    assert paths.cover_pdf.read_bytes().startswith(b"%PDF-")
    assert paths.cover_txt.read_text().startswith("Dear Hooli Hiring Team,\n\n")
    assert (result.selected, result.kept, result.roles, result.pages) == (2, 2, 2, 1)
    assert result.report.passed
    assert result.report.keywords_matched == ["Python", "Kafka", "PostgreSQL"]

    [event] = repo.query_audit(session, action="RESUME_TAILORED")
    assert (event.actor, event.status, event.target_id) == ("agent:tailor", "SUCCESS", row.id)
    assert event.details["keywords_matched"] == 3 and event.details["pages"] == 1
    assert event.duration_ms is not None


def test_tailor_failure_is_audited_and_writes_nothing(
    profile: CandidateProfile, session: Session, row: JobPosting, tmp_path: Path
) -> None:
    hallucinating = llm_for(DraftPlan(keywords=[], bullet_ids=["b_invented"]))
    with pytest.raises(TailorError, match="b_invented"):
        tailor_job(row, profile, hallucinating, tmp_path / "artifacts", session)

    assert not (tmp_path / "artifacts").exists()
    [event] = repo.query_audit(session, action="RESUME_TAILORED")
    assert event.status == "FAILURE" and "b_invented" in event.details["error"]


def test_failed_text_layer_check_is_not_saved(
    profile: CandidateProfile,
    session: Session,
    row: JobPosting,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failing = PdfReport(pages=1, checks={"linkedin": False}, problems=["LinkedIn URL not found"])
    monkeypatch.setattr("src.agents.tailor.runner.verify_pdf", lambda *_args: failing)
    with pytest.raises(TailorError, match="text-layer check failed: LinkedIn URL not found"):
        tailor_job(row, profile, llm_for(GOOD_PLAN), tmp_path / "artifacts", session)
    assert not (tmp_path / "artifacts").exists()


def test_tailor_refuses_roles_requiring_more_experience(
    profile: CandidateProfile, session: Session, tmp_path: Path
) -> None:
    senior = RawJobPosting("Principal Engineer", "Hooli", "San Francisco, CA", "https://x/2",
                           "Python. 25+ years of experience required.", "greenhouse")  # fmt: skip
    row = repo.upsert_job(session, senior, JobScore(90, "tier1_primary_market", 5))
    session.commit()
    with pytest.raises(TailorError, match="not eligible: experience: requires 25"):
        tailor_job(row, profile, llm_for(GOOD_PLAN), tmp_path / "artifacts", session)
    assert not (tmp_path / "artifacts").exists()
