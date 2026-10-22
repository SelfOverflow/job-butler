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
from tests.mock_ats import MockATS, mock_ats

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
ANSWERS = {
    "Why do you want to work at Hooli?": "Your mission.",
    "I agree to the privacy policy": "yes",
}


@pytest.fixture
def ats() -> Iterator[MockATS]:
    with mock_ats() as server:
        yield server


@pytest.fixture
def setup(
    ats: MockATS, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[TestClient, dict[str, str]]:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "profile.yaml").write_text(TEMPLATE.read_text())
    url = f"sqlite:///{tmp_path / 'jobs.db'}"
    engine = make_engine(url)
    init_db(engine)
    ids = {}
    with session_factory(engine)() as session:
        for name, page in (("form", "greenhouse_apply.html"), ("wall", "login_wall.html")):
            job = RawJobPosting(
                f"Engineer {name}",
                "Hooli",
                "San Francisco, CA",
                ats.url(page),
                "Python",
                "greenhouse",
            )
            ids[name] = repo.upsert_job(session, job, JobScore(90, "tier1_primary_market", 5)).id
        session.commit()
    engine.dispose()
    for job_id in ids.values():
        paths = artifact_paths(tmp_path / "artifacts", job_id)
        for path in (paths.resume, paths.cover_pdf, paths.cover_txt):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"%PDF-1.7")
    settings = Settings(
        _env_file=None,
        database_url=url,
        profile_path=tmp_path / "profile.yaml",
        artifacts_dir=tmp_path / "artifacts",
    )
    return TestClient(create_app(settings, frontend_dir=None)), ids


def test_hitl_flow_prepare_answer_approve(
    setup: tuple[TestClient, dict[str, str]], ats: MockATS
) -> None:
    client, ids = setup
    with client:
        prepared = client.post(f"/api/hitl/{ids['form']}/prepare").json()
        assert prepared["status"] == "needs_input"
        assert [q["label"] for q in prepared["questions"]] == list(ANSWERS)

        [pending] = client.get("/api/hitl/pending").json()
        assert (pending["job_id"], pending["title"], pending["company"]) == (
            ids["form"],
            "Engineer form",
            "Hooli",
        )
        assert pending["screenshot_url"] == f"/api/hitl/{ids['form']}/screenshot"
        shot = client.get(pending["screenshot_url"])
        assert shot.status_code == 200 and shot.content.startswith(b"\x89PNG")

        answered = client.post(f"/api/hitl/{ids['form']}/answers", json={"answers": ANSWERS}).json()
        assert answered["status"] == "awaiting_review" and answered["answers"] == ANSWERS
        assert ats.submissions == []  # answering never submits

        submitted = client.post(f"/api/hitl/{ids['form']}/approve").json()
        assert submitted["status"] == "submitted" and len(ats.submissions) == 1
        assert client.get("/api/hitl/pending").json() == []


def test_hitl_resolve_and_skip_endpoints(setup: tuple[TestClient, dict[str, str]]) -> None:
    client, ids = setup
    with client:
        blocked = client.post(f"/api/hitl/{ids['wall']}/prepare").json()
        assert (blocked["status"], blocked["barrier"]) == ("blocked", "ACCOUNT_CREATION_REQUIRED")
        assert (
            client.post(f"/api/hitl/{ids['wall']}/resolve").json()["status"] == "applied_manually"
        )
        assert client.post(f"/api/hitl/{ids['form']}/skip").json()["status"] == "skipped"
        events = client.get("/api/audit?actor=human:user").json()["items"]
        assert {e["action"] for e in events} == {
            "APPLICATION_MARKED_APPLIED",
            "APPLICATION_SKIPPED",
        }


def test_hitl_errors(setup: tuple[TestClient, dict[str, str]]) -> None:
    client, ids = setup
    with client:
        assert client.post(f"/api/hitl/{ids['form']}/approve").status_code == 409  # not prepared
        assert client.post("/api/hitl/job_00000000/skip").status_code == 404
        assert client.get(f"/api/hitl/{ids['form']}/screenshot").status_code == 404
        assert client.post("/api/hitl/not-a-job/prepare").status_code == 422
