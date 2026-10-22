from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.server.app import create_app

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}


@pytest.fixture
def profile_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    path = tmp_path / "profile" / "candidate_profile.yaml"
    path.parent.mkdir()
    path.write_text(TEMPLATE.read_text())
    return path


@pytest.fixture
def client(profile_path: Path, tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None, database_url=f"sqlite:///{tmp_path / 'jobs.db'}", profile_path=profile_path
    )
    with TestClient(create_app(settings, frontend_dir=None)) as c:
        yield c


def _backups(profile_path: Path) -> list[str]:
    folder = profile_path.parent / "backups"
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def test_get_profile_api(client: TestClient, profile_path: Path) -> None:
    body = client.get("/api/profile").json()
    assert body["yaml"] == profile_path.read_text()
    assert "${CANDIDATE_PHONE}" in body["yaml"]  # editor sees placeholders, not secrets
    assert body["profile"]["personal_info"]["full_name"] == "Jane Doe"
    assert body["errors"] == []


def test_get_profile_reports_errors_for_invalid_file(
    client: TestClient, profile_path: Path
) -> None:
    profile_path.write_text(
        profile_path.read_text().replace('full_name: "Jane Doe"', 'full_name: ""')
    )
    body = client.get("/api/profile").json()
    assert body["profile"] is None
    assert body["errors"][0]["loc"] == "personal_info.full_name"


def test_put_profile_api_success(client: TestClient, profile_path: Path) -> None:
    response = client.put("/api/profile", json={"set": {"preferences.min_base_salary": "180000"}})
    assert response.status_code == 200
    assert response.json()["profile"]["preferences"]["min_base_salary"] == 180000
    assert "min_base_salary: 180000" in profile_path.read_text()
    assert len(_backups(profile_path)) == 1


def test_put_profile_yaml_saves_text_verbatim(client: TestClient, profile_path: Path) -> None:
    edited = profile_path.read_text().replace('"Jane Doe"', '"Jane Q. Doe"') + "# my note\n"
    response = client.put("/api/profile", json={"yaml": edited})
    assert response.status_code == 200
    assert response.json()["profile"]["personal_info"]["full_name"] == "Jane Q. Doe"
    assert profile_path.read_text() == edited
    assert len(_backups(profile_path)) == 1


@pytest.mark.parametrize(
    ("body", "loc"),
    [
        ({"set": {"personal_info.email": "not-an-email"}}, "personal_info.email"),
        ({"set": {"preferences.not_a_field": "1"}}, "preferences.not_a_field"),
        ({"yaml": "personal_info: [unclosed"}, ""),
        ({"yaml": "- a list"}, ""),
        ({"set": {"work_experience.99.title": "x"}}, ""),
    ],
)
def test_put_profile_api_validation_error(
    client: TestClient, profile_path: Path, body: dict[str, object], loc: str
) -> None:
    before = profile_path.read_text()
    response = client.put("/api/profile", json=body)
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert errors and errors[0]["loc"] == loc and errors[0]["msg"]
    assert profile_path.read_text() == before and _backups(profile_path) == []


@pytest.mark.parametrize("body", [{}, {"yaml": "a: 1", "set": {"a": "1"}}])
def test_put_profile_requires_exactly_one_mode(client: TestClient, body: dict[str, object]) -> None:
    assert client.put("/api/profile", json=body).status_code == 422


def test_backups_and_restore(client: TestClient, profile_path: Path) -> None:
    original = profile_path.read_text()
    client.put("/api/profile", json={"set": {"work_experience.0.title": "Changed"}})
    [backup] = client.get("/api/profile/backups").json()
    assert backup["name"].startswith("candidate_profile_")

    response = client.post("/api/profile/restore", json={"name": backup["name"]})
    assert response.status_code == 200 and profile_path.read_text() == original
    missing = client.post("/api/profile/restore", json={"name": "../../etc/passwd"})
    assert missing.status_code == 404
