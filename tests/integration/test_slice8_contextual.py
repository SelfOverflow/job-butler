from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.ingestion.verifier import Liveness
from src.server.app import create_app
from src.storage import repository as repo

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "Springfield",
    "CANDIDATE_STATE": "State",
    "CANDIDATE_POSTAL_CODE": "00000",
}


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    prof = tmp_path / "candidate_profile.yaml"
    prof.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("PROFILE_PATH", str(prof))
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    settings = Settings(
        profile_path=prof,
        database_url=f"sqlite:///{db_path}",
        artifacts_dir=tmp_path / "artifacts",
    )
    app = create_app(settings, frontend_dir=None)
    with TestClient(app) as client:
        yield client


def test_profile_validate_endpoint(app_client: TestClient) -> None:
    res = app_client.get("/api/profile/validate")
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["full_name"] == "Jane Doe"
    assert data["bullet_count"] == 3


def test_profile_query_and_export_endpoints(app_client: TestClient) -> None:
    res = app_client.post(
        "/api/profile/query",
        json={"question": "Are you legally authorized to work in the United States?"},
    )
    assert res.status_code == 200
    assert res.json()["answer"] is True

    res_missing = app_client.post(
        "/api/profile/query",
        json={"question": "What is your favorite colour?"},
    )
    assert res_missing.status_code == 404

    res_export = app_client.get("/api/profile/export-master")
    assert res_export.status_code == 200
    assert "text/markdown" in res_export.headers["content-type"]
    assert "# Jane Doe" in res_export.text


def test_profile_add_bullet_endpoint(app_client: TestClient) -> None:
    res = app_client.post(
        "/api/profile/bullets",
        json={
            "role_id": "exp_company_alpha",
            "text": "Engineered distributed caching tier reducing latency by 45%",
            "skills": ["Redis", "Distributed Systems"],
        },
    )
    assert res.status_code == 200
    assert res.json()["bullet_id"].startswith("b_")


def test_scout_verify_single_job(app_client: TestClient) -> None:
    sessions = app_client.app.state.sessions
    with sessions() as session:
        job = RawJobPosting(
            "Engineer",
            "Acme",
            "Remote",
            "https://boards.greenhouse.io/acme/jobs/1",
            "desc",
            "greenhouse",
        )
        row = repo.upsert_job(session, job, JobScore(score=88, tier="Tier 1", boost=5))
        job_id = row.id
        session.commit()

    with patch("src.services.scout.verifier_verify", return_value=Liveness("live", "ok")):
        res = app_client.post("/api/commands/scout_verify", json={"job_id": job_id})
        assert res.status_code == 202
        run_id = res.json()["run_id"]

        import time
        for _ in range(40):
            res_run = app_client.get(f"/api/commands/runs/{run_id}")
            if res_run.json()["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.05)

        data = res_run.json()
        assert data["status"] == "succeeded"
        assert data["result"]["status"] == "live"
