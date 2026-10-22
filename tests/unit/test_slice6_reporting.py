from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.analytics.market import Demand, MarketSnapshot, Upskill
from src.cli import app
from src.config.settings import Settings
from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.server.app import create_app
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory
from src.storage.models import ApplicationStatus

SNAPSHOT = MarketSnapshot(
    total=412,
    matched=34,
    threshold=60,
    demand=[Demand("Python", 346, 84.0, True), Demand("Kubernetes", 210, 51.0, False)],
    upskill=[Upskill("Kubernetes", 14, 210, 41.2), Upskill("Terraform", 8, 120, 23.5)],
)


def _db(tmp_path: Path, with_snapshot: bool = True) -> str:
    url = f"sqlite:///{tmp_path / 'jobs.db'}"
    engine = make_engine(url)
    init_db(engine)
    with session_factory(engine)() as session:
        for n in range(3):
            job = RawJobPosting(f"Role {n}", "Hooli", "Remote", f"https://x/{n}", "Python", "lever")
            repo.upsert_job(session, job, JobScore(80, None, 0))
        first = repo.list_active(session)[0].id
        repo.save_application(session, first, status=ApplicationStatus.AWAITING_REVIEW)
        if with_snapshot:
            repo.save_market_snapshot(session, SNAPSHOT)
        session.commit()
    engine.dispose()
    return url


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, database_url=_db(tmp_path))
    with TestClient(create_app(settings, frontend_dir=None)) as c:
        yield c


def test_analytics_api_endpoints(client: TestClient) -> None:
    trends = client.get("/api/analytics/trends").json()
    assert (trends["total"], trends["matched"], trends["threshold"]) == (412, 34, 60)
    assert trends["created_at"] is not None
    assert trends["demand"][0] == {"skill": "Python", "postings": 346, "share": 84.0, "have": True}

    upskill = client.get("/api/analytics/upskill").json()
    assert upskill["upskill"][0] == {
        "skill": "Kubernetes",
        "unlocks": 14,
        "demand": 210,
        "uplift_pct": 41.2,
    }
    assert upskill["matched"] == 34


def test_analytics_api_before_any_sweep(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, database_url=_db(tmp_path, with_snapshot=False))
    with TestClient(create_app(settings, frontend_dir=None)) as c:
        trends = c.get("/api/analytics/trends").json()
        assert (trends["created_at"], trends["demand"]) == (None, [])
        assert c.get("/api/analytics/upskill").json()["upskill"] == []


def test_cli_analytics_report_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", _db(tmp_path))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    result = CliRunner().invoke(app, ["analytics", "report"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "Career Intelligence Report" in out
    assert "Market: 412 eligible postings | 34 matched (fit score >= 60)" in out
    assert "Pipeline: 3 active jobs | 0 tailored | applications: 1 awaiting review" in out
    assert "Python 84% ✓" in out and "Kubernetes 51% ✗" in out
    assert "1. Kubernetes: unlocks 14 roles (+41.2% vs 34 matched; in 210 postings)" in out


def test_cli_report_before_any_sweep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", _db(tmp_path, with_snapshot=False))
    result = CliRunner().invoke(app, ["analytics", "report"])
    assert (
        result.exit_code == 0
        and "No market snapshot yet: run `job-butler scout run`" in result.output
    )
