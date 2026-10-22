from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.server.app import create_app

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "Springfield",
    "CANDIDATE_STATE": "State",
    "CANDIDATE_POSTAL_CODE": "00000",
}


def test_settings_never_expose_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    prof = tmp_path / "candidate_profile.yaml"
    prof.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    secret_key = "super_secret_api_key_12345"
    settings = Settings(
        profile_path=prof,
        database_url=f"sqlite:///{tmp_path / 'jobs.db'}",
        gemini_api_key=secret_key,
        firecrawl_api_key=secret_key,
        auth_disabled=True,
    )
    app = create_app(settings, frontend_dir=None)
    with TestClient(app) as client:
        res = client.get("/api/settings")
        assert res.status_code == 200
        data = res.json()
        assert secret_key not in res.text
        assert data["gemini_configured"] is True
        assert data["firecrawl_configured"] is True
        assert "gemini_api_key" not in data
        assert "firecrawl_api_key" not in data
