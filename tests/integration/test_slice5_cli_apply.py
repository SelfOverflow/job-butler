from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.agents.tailor.runner import artifact_paths
from src.cli import app
from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory
from tests.mock_ats import MockATS, mock_ats

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
WHY = "Why do you want to work at Hooli?"
PRIVACY = "I agree to the privacy policy"


@pytest.fixture
def ats() -> Iterator[MockATS]:
    with mock_ats() as server:
        yield server


@pytest.fixture
def job_id(ats: MockATS, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.chdir(tmp_path)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "profile.yaml").write_text(TEMPLATE.read_text())
    monkeypatch.setenv("PROFILE_PATH", str(tmp_path / "profile.yaml"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'jobs.db'}")
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    with session_factory(engine)() as session:
        job = RawJobPosting(
            "Senior Engineer",
            "Hooli",
            "San Francisco, CA",
            ats.url("greenhouse_apply.html"),
            "Python",
            "greenhouse",
        )
        row = repo.upsert_job(session, job, JobScore(90, "tier1_primary_market", 5))
        session.commit()
        job_id = row.id
    engine.dispose()
    paths = artifact_paths(tmp_path / "artifacts", job_id)
    for path in (paths.resume, paths.cover_pdf, paths.cover_txt):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.7")
    return job_id


def _invoke(*args: str, exit_code: int = 0, input: str | None = None) -> str:
    result = CliRunner().invoke(app, ["apply", *args], input=input)
    assert result.exit_code == exit_code, result.output
    return result.output


def test_apply_prepares_and_lists_questions(job_id: str, ats: MockATS) -> None:
    out = _invoke("--job-id", job_id)
    assert "[!] Needs input: 2 question(s) the profile cannot answer" in out
    assert f"- {WHY}" in out and f"- {PRIVACY}" in out
    assert "Nothing was submitted" in out
    assert ats.submissions == []
    assert job_id in _invoke("list") and "needs_input" in _invoke("list")


def test_answers_then_approve_with_confirmation(job_id: str, ats: MockATS) -> None:
    out = _invoke(
        "--job-id", job_id, "--answer", f"{WHY}=Your mission.", "--answer", f"{PRIVACY}=yes"
    )
    assert "[✓] Ready for review" in out and f"job-butler apply approve {job_id}" in out

    declined = _invoke("approve", job_id, input="n\n", exit_code=1)
    assert "First Name: Jane" in declined and "Not submitted" in declined
    assert ats.submissions == []

    out = _invoke("approve", job_id, input="y\n")
    assert "[✓] Submitted" in out and len(ats.submissions) == 1
    assert "No pending applications" in _invoke("list")


def test_approve_yes_skips_prompt_and_errors_are_readable(job_id: str, ats: MockATS) -> None:
    assert "Cannot approve" in _invoke("approve", job_id, "--yes", exit_code=1)  # not prepared yet
    _invoke("--job-id", job_id, "--answer", f"{WHY}=Mission.", "--answer", f"{PRIVACY}=yes")
    assert "[✓] Submitted" in _invoke("approve", job_id, "--yes")
    assert "already submitted" in _invoke("--job-id", job_id, exit_code=1)


def test_skip_and_mark_applied(job_id: str) -> None:
    assert "[✓] Skipped" in _invoke("skip", job_id)
    assert "[✓] Marked as applied" in _invoke("mark-applied", job_id)
    assert "No job with id" in _invoke("skip", "job_00000000", exit_code=1)


def test_malformed_answer(job_id: str) -> None:
    assert "Expected QUESTION=ANSWER" in _invoke(
        "--job-id", job_id, "--answer", "oops", exit_code=1
    )
