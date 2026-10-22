from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.config.settings import Settings
from src.server.app import create_app
from src.server.auth import COOKIE_NAME, hash_password, login_limiter

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "Springfield",
    "CANDIDATE_STATE": "State",
    "CANDIDATE_POSTAL_CODE": "00000",
}


def test_auth_disabled_only_on_localhost(tmp_path: Path) -> None:
    prof = tmp_path / "candidate_profile.yaml"
    prof.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    settings = Settings(
        profile_path=prof,
        database_url=f"sqlite:///{tmp_path / 'jobs.db'}",
        auth_disabled=True,
        host="0.0.0.0",
    )
    with pytest.raises(ValueError, match="AUTH_DISABLED=true is only allowed on loopback"):
        create_app(settings, frontend_dir=None)


def test_auth_required_for_api_and_websocket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    prof = tmp_path / "candidate_profile.yaml"
    prof.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")

    password = "CorrectHorseBatteryStaple"
    settings = Settings(
        profile_path=prof,
        database_url=f"sqlite:///{tmp_path / 'jobs.db'}",
        auth_disabled=False,
        dashboard_password_hash=hash_password(password),
        session_secret="super-session-secret-key-1234",
    )
    app = create_app(settings, frontend_dir=None)
    with TestClient(app) as client:
        # Public health endpoint works without auth
        res_health = client.get("/health")
        assert res_health.status_code == 200

        # Protected API returns 401 without session
        res_jobs = client.get("/api/jobs")
        assert res_jobs.status_code == 401

        # WebSocket rejects unauthenticated connection
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/events") as ws:
                ws.receive_json()

        # Login rate limiting: 5 bad attempts triggers 429
        login_limiter._attempts.clear()
        for _ in range(5):
            res_bad = client.post("/api/auth/login", json={"password": "wrong"})
            assert res_bad.status_code == 401

        res_rate = client.post("/api/auth/login", json={"password": "wrong"})
        assert res_rate.status_code == 429

        # Successful login after rate limit cleared
        login_limiter._attempts.clear()
        res_login = client.post("/api/auth/login", json={"password": password})
        assert res_login.status_code == 200
        csrf_token = res_login.json()["csrf_token"]
        assert COOKIE_NAME in client.cookies

        # Protected GET now succeeds with cookie
        res_jobs_auth = client.get("/api/jobs")
        assert res_jobs_auth.status_code == 200

        # Mutation without CSRF token header fails with 403
        res_mutation_no_csrf = client.post(
            "/api/commands/scout_sweep", json={"limit": 5}
        )
        assert res_mutation_no_csrf.status_code == 403

        # Mutation with CSRF token header succeeds (202)
        res_mutation_csrf = client.post(
            "/api/commands/scout_sweep",
            json={"limit": 5},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert res_mutation_csrf.status_code == 202

        # Logout clears session cookie
        res_logout = client.post("/api/auth/logout")
        assert res_logout.status_code == 200
        assert client.cookies.get(COOKIE_NAME) is None

        # Subsequent protected GET is 401
        res_jobs_after = client.get("/api/jobs")
        assert res_jobs_after.status_code == 401
