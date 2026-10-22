from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.server.app import create_app
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'jobs.db'}"
    engine = make_engine(url)
    init_db(engine)
    with session_factory(engine)() as session:
        for i in range(25):
            repo.record_audit(
                session,
                actor="agent:scout",
                action="JOB_DISCOVERED",
                status="SUCCESS",
                target_id=f"old{i}",
            )
        session.commit()
    engine.dispose()
    return url


@pytest.fixture
def client(db_url: str) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, database_url=db_url, event_poll_seconds=0.02)
    with TestClient(create_app(settings, frontend_dir=None)) as c:
        yield c


def _record(db_url: str, action: str) -> None:
    engine = make_engine(db_url)  # A separate "process" writing to the shared database.
    with session_factory(engine)() as session:
        repo.record_audit(
            session, actor="agent:tailor", action=action, status="SUCCESS", target_id="job_1"
        )
        session.commit()
    engine.dispose()


def test_websocket_sends_recent_snapshot_on_connect(client: TestClient) -> None:
    with client.websocket_connect("/ws/events") as ws:
        message = ws.receive_json()
    assert message["type"] == "snapshot"
    events = message["events"]
    assert len(events) == 20
    assert events[0]["target_id"] == "old24"  # newest first


def test_websocket_event_broadcasting(client: TestClient, db_url: str) -> None:
    with (
        client.websocket_connect("/ws/events") as first,
        client.websocket_connect("/ws/events") as second,
    ):
        first.receive_json(), second.receive_json()  # snapshots
        _record(db_url, "RESUME_TAILORED")
        for ws in (first, second):
            message = ws.receive_json()
            assert message["type"] == "audit"
            assert (message["event"]["action"], message["event"]["actor"]) == (
                "RESUME_TAILORED",
                "agent:tailor",
            )
            assert "timestamp" in message["event"] and "details" in message["event"]


def test_events_arrive_in_order_and_only_once(client: TestClient, db_url: str) -> None:
    with client.websocket_connect("/ws/events") as ws:
        ws.receive_json()
        _record(db_url, "A")
        _record(db_url, "B")
        actions = [ws.receive_json()["event"]["action"] for _ in range(2)]
        _record(db_url, "C")
        assert actions == ["A", "B"]
        assert ws.receive_json()["event"]["action"] == "C"  # A and B are not re-sent


def test_disconnected_clients_are_dropped(client: TestClient, db_url: str) -> None:
    with client.websocket_connect("/ws/events") as ws:
        ws.receive_json()
    _record(db_url, "AFTER_DISCONNECT")  # Broadcasting to a closed socket must not crash the bus.
    with client.websocket_connect("/ws/events") as ws:
        snapshot = ws.receive_json()
        assert snapshot["events"][0]["action"] in ("AFTER_DISCONNECT", "JOB_DISCOVERED")
    assert client.get("/health").status_code == 200
