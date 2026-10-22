from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.scheduler.autopilot import Stage

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}


def test_cli_autopilot_once_and_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "profile.yaml").write_text(TEMPLATE.read_text())
    monkeypatch.setenv("PROFILE_PATH", str(tmp_path / "profile.yaml"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'jobs.db'}")
    fake = [
        Stage("sweep", lambda _p: "discovered 3"),
        Stage("tailor", lambda _p: "tailored 1, failed 0"),
    ]
    monkeypatch.setattr("src.cli_autopilot.build_stages", lambda *_a, **_k: fake)

    assert (
        "No autopilot cycle has run yet" in CliRunner().invoke(app, ["autopilot", "status"]).output
    )
    result = CliRunner().invoke(app, ["autopilot", "start", "--once"])
    assert result.exit_code == 0, result.output
    assert "[✓] Cycle 1: sweep: discovered 3 | tailor: tailored 1, failed 0" in result.output
    status = CliRunner().invoke(app, ["autopilot", "status"]).output
    assert (
        "Last cycle" in status and "SUCCESS" in status and "tailor: tailored 1, failed 0" in status
    )
