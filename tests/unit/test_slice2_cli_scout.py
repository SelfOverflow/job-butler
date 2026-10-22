from collections.abc import Iterator
from pathlib import Path

import pytest
import respx
from typer.testing import CliRunner

from src.cli import app
from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory
from src.storage.models import utcnow

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
JOB_URL = "https://boards.greenhouse.io/hooli/jobs/1"
BOARD = "https://boards-api.greenhouse.io/v1/boards/hooli/jobs"


def _job(title: str, location: str, url: str = JOB_URL) -> RawJobPosting:
    return RawJobPosting(title, "Hooli", location, url, "Python", "greenhouse")


@pytest.fixture
def db_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.chdir(tmp_path)  # No developer .env, profile, or database.
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        TEMPLATE.read_text().replace(
            "  watched_companies: []",
            '  watched_companies:\n    - {name: "Hooli", ats: "greenhouse", board: "hooli"}',
        )
    )
    monkeypatch.setenv("PROFILE_PATH", str(profile))
    url = f"sqlite:///{tmp_path / 'jobs.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    return url


def _seed(db_url: str, *jobs: tuple[RawJobPosting, JobScore, bool]) -> None:
    engine = make_engine(db_url)
    init_db(engine)
    with session_factory(engine)() as session:
        for job, score, verified in jobs:
            row = repo.upsert_job(session, job, score)
            row.last_verified_at = utcnow() if verified else None
        session.commit()
    engine.dispose()


def _invoke(*args: str, exit_code: int = 0) -> str:
    result = CliRunner().invoke(app, ["scout", *args])
    assert result.exit_code == exit_code, result.output
    return result.output


@pytest.fixture
def http() -> Iterator[None]:
    with respx.mock:
        yield


def test_cli_scout_list_command(db_url: str) -> None:
    assert "No active jobs yet" in _invoke("list")
    _seed(
        db_url,
        (_job("Tech Lead", "New York, NY"), JobScore(94, "tier1_primary_market", 5), True),
        (_job("Software Engineer", "Lagos", url=JOB_URL + "2"), JobScore(40, None, 0), False),
    )

    lines = _invoke("list").splitlines()
    assert lines[0].split() == [
        "ID",
        "Score",
        "Tier",
        "Company",
        "Title",
        "Location",
        "Active",
        "Source",
    ]
    assert set(lines[1]) == {"-"}
    assert lines[2].split()[1:4] == ["94", "Tier", "1"] and "[LIVE]" in lines[2]
    assert "Tech Lead" in lines[2] and "greenhouse" in lines[2]
    assert "-" in lines[3].split()[2] and "[?]" in lines[3]  # no tier, not yet verified
    assert len(_invoke("list", "--min-score", "50").splitlines()) == 3


def test_cli_scout_run_saves_and_lists_jobs(db_url: str, http: None) -> None:
    respx.get(BOARD).respond(
        200,
        json={
            "jobs": [
                {
                    "title": "Senior Software Engineer",
                    "location": {"name": "San Francisco, CA"},
                    "absolute_url": JOB_URL,
                    "content": "Python FastAPI Docker",
                }
            ]
        },
    )
    respx.get(JOB_URL).respond(200, html="<h1>Apply</h1>")

    out = _invoke("run", "--limit", "5")

    assert "FIRECRAWL_API_KEY not set" in out
    assert "Discovered 1" in out and "saved 1 (1 new)" in out
    assert "Senior Software Engineer" in _invoke("list")


def test_cli_scout_run_reports_discovery_errors(db_url: str, http: None) -> None:
    respx.get(BOARD).respond(503)
    out = _invoke("run")
    assert "saved 0" in out and "[!] Hooli (greenhouse/hooli)" in out


def test_cli_scout_run_with_invalid_profile(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CANDIDATE_PHONE")
    assert "CANDIDATE_PHONE" in _invoke("run", exit_code=1)


def test_cli_scout_verify_command(db_url: str, http: None) -> None:
    _seed(
        db_url, (_job("Tech Lead", "New York, NY"), JobScore(94, "tier1_primary_market", 5), True)
    )
    respx.get(JOB_URL).respond(404)
    assert "live 0, closed 1, unknown 0" in _invoke("verify")
    assert "No active jobs yet" in _invoke("list")
