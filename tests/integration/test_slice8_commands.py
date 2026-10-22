from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.ingestion.pipeline import SweepReport
from src.server.app import create_app
from src.storage.models import CommandStatus

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


def test_command_params_validation(app_client: TestClient) -> None:
    res = app_client.post("/api/commands/unknown_command", json={})
    assert res.status_code == 404

    res = app_client.post("/api/commands/scout_sweep", json={"limit": "not_an_int"})
    assert res.status_code == 422


def test_command_run_lifecycle_and_single_flight(app_client: TestClient) -> None:
    import time
    fake_report = SweepReport(discovered=10, saved=5, new=3)

    def slow_sweep(*args: Any, **kwargs: Any) -> SweepReport:
        progress = kwargs.get("progress")
        if progress:
            progress("search", 1, 2, "query")
        time.sleep(0.15)
        return fake_report

    with patch("src.services.scout.run_sweep", side_effect=slow_sweep):
        res = app_client.post("/api/commands/scout_sweep", json={"limit": 5})
        assert res.status_code == 202
        data = res.json()
        run_id = data["run_id"]

        # Duplicate request returns the same run while active (single-flight)
        res_dup = app_client.post("/api/commands/scout_sweep", json={"limit": 5})
        assert res_dup.status_code == 202
        assert res_dup.json()["run_id"] == run_id

        # Poll until complete
        for _ in range(50):
            res_get = app_client.get(f"/api/commands/runs/{run_id}")
            assert res_get.status_code == 200
            run_data = res_get.json()
            if run_data["status"] in (CommandStatus.SUCCEEDED, CommandStatus.FAILED):
                break
            time.sleep(0.05)

        assert run_data["status"] == CommandStatus.SUCCEEDED
        assert run_data["result"]["saved"] == 5

        # Check in history
        res_list = app_client.get("/api/commands/runs")
        assert res_list.status_code == 200
        runs = res_list.json()
        assert any(r["id"] == run_id for r in runs)


def test_cancel_running_command(app_client: TestClient) -> None:
    import time

    def slow_sweep(*args: Any, **kwargs: Any) -> SweepReport:
        progress = kwargs.get("progress")
        for _ in range(30):
            if progress:
                progress("search", 1, 10, "query")
            time.sleep(0.05)
        return SweepReport()

    with patch("src.services.scout.run_sweep", side_effect=slow_sweep):
        res = app_client.post("/api/commands/scout_sweep", json={"limit": 5})
        run_id = res.json()["run_id"]

        time.sleep(0.05)
        # Cancel the run
        res_cancel = app_client.post(f"/api/commands/runs/{run_id}/cancel")
        assert res_cancel.status_code == 200
        assert res_cancel.json() == {"status": "cancelling"}

        # Wait for cancelled state
        for _ in range(50):
            res_get = app_client.get(f"/api/commands/runs/{run_id}")
            if res_get.json()["status"] == CommandStatus.CANCELLED:
                break
            time.sleep(0.05)

        assert res_get.json()["status"] == CommandStatus.CANCELLED
