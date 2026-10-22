import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.ingestion.pipeline import SweepReport
from src.server.app import create_app

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
        event_poll_seconds=0.02,
    )
    app = create_app(settings, frontend_dir=None)
    with TestClient(app) as client:
        yield client


def test_command_progress_broadcast_over_websocket(app_client: TestClient) -> None:
    fake_report = SweepReport(discovered=10, saved=5, new=3)

    def slow_sweep(*args: Any, **kwargs: Any) -> SweepReport:
        progress = kwargs.get("progress")
        if progress:
            progress("search", 1, 2, "query")
        time.sleep(0.05)
        return fake_report

    with app_client.websocket_connect("/ws/events") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "snapshot"

        with patch("src.services.scout.run_sweep", side_effect=slow_sweep):
            res = app_client.post("/api/commands/scout_sweep", json={"limit": 5})
            assert res.status_code == 202
            run_id = res.json()["run_id"]

            received_commands = []
            while True:
                msg = ws.receive_json()
                if msg.get("type") == "command":
                    received_commands.append(msg)
                    if (
                        msg["run"]["id"] == run_id
                        and msg["run"]["status"] in ("succeeded", "failed")
                    ):
                        break

            assert len(received_commands) >= 2
            statuses = [m["run"]["status"] for m in received_commands]
            assert "running" in statuses or "succeeded" in statuses
            final = received_commands[-1]["run"]
            assert final["status"] == "succeeded"
            assert final["result"]["saved"] == 5
