from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.agents.tailor.runner import artifact_paths
from src.config.settings import Settings
from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.server.app import create_app
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}


def _job(title: str, n: int) -> RawJobPosting:
    return RawJobPosting(title, "Hooli", "San Francisco, CA", f"https://x/{n}", "Python", "lever")


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.chdir(tmp_path)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "profile.yaml").write_text(TEMPLATE.read_text())
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'jobs.db'}",
        artifacts_dir=tmp_path / "artifacts",
        profile_path=tmp_path / "profile.yaml",
    )


@pytest.fixture
def ids(settings: Settings) -> dict[str, str]:
    engine = make_engine(settings.database_url)
    init_db(engine)
    with session_factory(engine)() as session:
        top = repo.upsert_job(
            session, _job("Tech Lead", 1), JobScore(94, "tier1_primary_market", 5)
        )
        low = repo.upsert_job(session, _job("Engineer", 2), JobScore(40, None, 0))
        gone = repo.upsert_job(session, _job("Old Role", 3), JobScore(70, None, 0))
        repo.mark_inactive(session, gone.id)
        for i in range(3):
            repo.record_audit(
                session,
                actor="agent:scout",
                action="JOB_DISCOVERED",
                status="SUCCESS",
                target_id=f"j{i}",
            )
        repo.record_audit(
            session,
            actor="human:user",
            action="PROFILE_UPDATED",
            status="WARNING",
            details={"k": 1},
        )
        session.commit()
        result = {"top": top.id, "low": low.id, "gone": gone.id}
    engine.dispose()
    return result


@pytest.fixture
def client(settings: Settings, ids: dict[str, str]) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c


def test_server_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200 and response.json() == {"status": "ok"}


def test_jobs_list_api(client: TestClient, ids: dict[str, str], settings: Settings) -> None:
    paths = artifact_paths(settings.artifacts_dir, ids["top"])
    paths.resume.parent.mkdir(parents=True)
    paths.resume.write_bytes(b"%PDF-1.7 fake")

    jobs = client.get("/api/jobs").json()

    assert [j["id"] for j in jobs] == [ids["top"], ids["low"]]  # inactive hidden, score desc
    top = jobs[0]
    assert (top["score"], top["tier"], top["tier_label"], top["company"]) == (
        94,
        "tier1_primary_market",
        "Tier 1",
        "Hooli",
    )
    assert top["resume_url"] == f"/api/artifacts/{ids['top']}/resume"
    assert top["cover_letter_url"] is None and jobs[1]["resume_url"] is None
    assert [j["id"] for j in client.get("/api/jobs?min_score=50").json()] == [ids["top"]]
    assert len(client.get("/api/jobs?include_inactive=true").json()) == 3


def test_job_detail_and_artifact_download(
    client: TestClient, ids: dict[str, str], settings: Settings
) -> None:
    detail = client.get(f"/api/jobs/{ids['top']}").json()
    assert detail["description"] == "Python" and detail["url"] == "https://x/1"
    assert client.get("/api/jobs/job_deadbeef").status_code == 404

    url = f"/api/artifacts/{ids['top']}/resume"
    assert client.get(url).status_code == 404  # not tailored yet
    paths = artifact_paths(settings.artifacts_dir, ids["top"])
    paths.resume.parent.mkdir(parents=True)
    paths.resume.write_bytes(b"%PDF-1.7 fake")
    response = client.get(url)
    assert response.status_code == 200 and response.content == b"%PDF-1.7 fake"
    assert response.headers["content-type"] == "application/pdf"


@pytest.mark.parametrize(
    "path", ["/api/artifacts/..%2F..%2Fetc/resume", "/api/artifacts/job_1234abcd/passwd"]
)
def test_artifact_route_rejects_bad_input(client: TestClient, path: str) -> None:
    assert client.get(path).status_code in (404, 422)
