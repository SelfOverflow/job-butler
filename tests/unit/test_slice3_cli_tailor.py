from pathlib import Path

import pytest
from pydantic import BaseModel
from typer.testing import CliRunner

from src.agents.llm import LLMError
from src.agents.tailor.cover_letter import CoverLetterDraft
from src.agents.tailor.drafter import DraftPlan
from src.cli import app
from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory
from tests.fakes import FakeLLM

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
JD = "Python, FastAPI, Kafka and PostgreSQL."
LETTER = CoverLetterDraft(
    greeting="Dear Team,", paragraphs=["I would love to help."], closing="Best,"
)


def _job(title: str, url: str) -> RawJobPosting:
    return RawJobPosting(title, "Hooli", "San Francisco, CA", url, JD, "greenhouse")


def _llm(bullet_ids: list[str]) -> FakeLLM:
    def respond(prompt: str, schema: type[BaseModel]) -> BaseModel:
        if schema is CoverLetterDraft:
            return LETTER
        ids = ["b_invented"] if "Doomed" in prompt else bullet_ids
        return DraftPlan(keywords=["Python", "Kafka"], bullet_ids=ids)

    return FakeLLM(respond)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.chdir(tmp_path)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "profile.yaml").write_text(TEMPLATE.read_text())
    monkeypatch.setenv("PROFILE_PATH", str(tmp_path / "profile.yaml"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'jobs.db'}")
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(
        "src.cli_tailor.make_llm", lambda _settings: _llm(["b_alpha_1", "b_beta_1"])
    )

    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    ids = {}
    with session_factory(engine)() as session:
        for title, score in (
            ("Senior Backend Engineer", 94),
            ("Doomed Role", 80),
            ("Junior Role", 40),
        ):
            row = repo.upsert_job(
                session,
                _job(title, f"https://x/{score}"),
                JobScore(score, "tier1_primary_market", 5),
            )
            ids[title] = row.id
        session.commit()
    engine.dispose()
    return ids


def _invoke(*args: str, exit_code: int = 0) -> str:
    result = CliRunner().invoke(app, ["tailor", *args])
    assert result.exit_code == exit_code, result.output
    return result.output


def test_tailor_single_job(env: dict[str, str], tmp_path: Path) -> None:
    job_id = env["Senior Backend Engineer"]
    out = _invoke("--job-id", job_id)

    assert "[✓] Fit score: 94 (Tier 1)" in out
    assert "[✓] Drafter: 2 bullets selected across 2 roles, 2 kept (1-page budget met)" in out
    assert "[✓] Reviewer: every bullet verified verbatim against the profile" in out
    assert (
        "[✓] Text-layer check: 2/2 keywords matched; LinkedIn, email and phone extractable" in out
    )
    resume = tmp_path / "artifacts" / "resumes" / f"{job_id}_resume.pdf"
    assert f"[✓] Resume: {resume}" in out and resume.exists()
    assert (tmp_path / "artifacts" / "cover_letters" / f"{job_id}_cover.txt").exists()


def test_tailor_unknown_job_and_missing_target(env: dict[str, str]) -> None:
    assert "No job with id job_missing" in _invoke("--job-id", "job_missing", exit_code=1)
    assert "--job-id or --all-matches" in _invoke(exit_code=1)


def test_tailor_requires_gemini_key(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    def no_key(_settings: object) -> FakeLLM:
        raise LLMError("GEMINI_API_KEY is not set")

    monkeypatch.setattr("src.cli_tailor.make_llm", no_key)
    out = _invoke("--job-id", env["Senior Backend Engineer"], exit_code=1)
    assert "[✗] GEMINI_API_KEY is not set" in out


def test_tailor_all_matches_continues_past_failures(env: dict[str, str]) -> None:
    out = _invoke("--all-matches", "--min-score", "75", exit_code=1)
    assert f"[✗] {env['Doomed Role']}" in out and "b_invented" in out
    assert "Tailored 1 of 2 job(s); 1 failed" in out
    assert env["Junior Role"] not in out  # below --min-score


def test_verify_pdf_command(env: dict[str, str], tmp_path: Path) -> None:
    _invoke("--job-id", env["Senior Backend Engineer"])
    resume = tmp_path / "artifacts" / "resumes" / f"{env['Senior Backend Engineer']}_resume.pdf"
    out = _invoke("verify-pdf", str(resume))
    assert "[✓] text" in out and "[✓] linkedin" in out and "1 page(s)" in out

    junk = tmp_path / "junk.pdf"
    junk.write_bytes(b"not a pdf")
    assert "[✗] text" in _invoke("verify-pdf", str(junk), exit_code=1)
    assert "not found" in _invoke("verify-pdf", str(tmp_path / "missing.pdf"), exit_code=1)
