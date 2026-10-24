from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.agents.navigator.field_mapper import FieldSpec, FillPlan, PlannedField
from src.config.settings import Settings
from src.server.app import create_app
from src.storage.database import init_db, make_engine, session_factory
from src.storage.models import ApplicationRecord, ApplicationStatus, JobPosting


@pytest.fixture
def client_and_session(tmp_path: Path) -> tuple[TestClient, Callable[[], MagicMock]]:
    db_path = tmp_path / "test.db"
    url = f"sqlite:///{db_path}"
    engine = make_engine(url)
    init_db(engine)
    sessions = session_factory(engine)
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text("personal_info:\n  full_name: Test Candidate\n")
    settings = Settings(
        _env_file=None,
        database_url=url,
        profile_path=profile_path,
        artifacts_dir=tmp_path / "artifacts",
    )
    client = TestClient(create_app(settings, frontend_dir=None))
    return client, sessions


def test_get_application_by_id(
    client_and_session: tuple[TestClient, Callable[[], MagicMock]],
) -> None:
    client, sessions = client_and_session
    with sessions() as session:
        job = JobPosting(
            id="job_1234abcd",
            content_key="key1234abcd",
            title="Senior Engineer",
            company="Acme Corp",
            location="Remote",
            url="https://example.com/apply",
            description="Build cool things",
            source="manual",
            score=85,
            tier="tier1",
            boost=5,
        )
        session.add(job)
        session.flush()
        app = ApplicationRecord(
            job_id="job_1234abcd",
            status=ApplicationStatus.AWAITING_REVIEW,
            plan=[
                {"label": "Email", "kind": "text", "value": "test@example.com", "source": "profile"}
            ],
            questions=[],
            answers={},
        )
        session.add(app)
        session.commit()

    with client:
        # Successful retrieval
        res = client.get("/api/hitl/job_1234abcd")
        assert res.status_code == 200
        data = res.json()
        assert data["job_id"] == "job_1234abcd"
        assert data["title"] == "Senior Engineer"
        assert data["company"] == "Acme Corp"
        assert data["status"] == "awaiting_review"
        assert len(data["plan"]) == 1

        # 404 for nonexistent job id
        res_404 = client.get("/api/hitl/job_00000000")
        assert res_404.status_code == 404

        # 422 for malformed job id
        res_422 = client.get("/api/hitl/invalid-id")
        assert res_422.status_code == 422


def test_list_all_applications(
    client_and_session: tuple[TestClient, Callable[[], MagicMock]],
) -> None:
    client, sessions = client_and_session
    statuses = [
        ApplicationStatus.AWAITING_REVIEW,
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.SKIPPED,
    ]
    with sessions() as session:
        for i, status in enumerate(statuses):
            jid = f"job_0000000{i}"
            job = JobPosting(
                id=jid,
                content_key=f"key_{i}",
                title=f"Role {i}",
                company=f"Company {i}",
                location="Remote",
                url="https://example.com/apply",
                description="desc",
                source="manual",
                score=80 + i,
                tier="tier1",
                boost=0,
            )
            session.add(job)
            session.flush()
            app = ApplicationRecord(
                job_id=jid,
                status=status,
                plan=[],
                questions=[],
                answers={},
            )
            session.add(app)
        session.commit()

    with client:
        # List all
        res = client.get("/api/hitl/applications")
        assert res.status_code == 200
        all_apps = res.json()
        assert len(all_apps) == 3

        # Filter by status
        res_sub = client.get("/api/hitl/applications?status=submitted")
        assert res_sub.status_code == 200
        sub_apps = res_sub.json()
        assert len(sub_apps) == 1
        assert sub_apps[0]["status"] == "submitted"


def test_fill_form_with_progress_callback() -> None:
    from src.agents.navigator.form_inspector import fill_form

    page = MagicMock()
    spec1 = FieldSpec("name", "Full Name", "text", True, (), (), "#name")
    spec2 = FieldSpec("email", "Email Address", "text", True, (), (), "#email")
    plan = FillPlan(
        planned=(
            PlannedField(spec1, "Mohit Ranjan", "profile"),
            PlannedField(spec2, "mohit@example.com", "profile"),
        ),
        unanswered=(),
    )
    steps: list[tuple[int, int, str, str]] = []
    fill_form(page, plan, on_step=lambda i, tot, lbl, kind: steps.append((i, tot, lbl, kind)))

    assert len(steps) == 2
    assert steps[0] == (1, 2, "Full Name", "text")
    assert steps[1] == (2, 2, "Email Address", "text")
    assert page.fill.call_count == 2
