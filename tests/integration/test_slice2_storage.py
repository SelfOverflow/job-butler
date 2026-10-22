from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory

JOB = RawJobPosting(
    title="Senior Engineer",
    company="Hooli",
    location="Bengaluru, India",
    url="https://boards.greenhouse.io/hooli/jobs/1",
    description="Python and React.",
    source="greenhouse",
)
SCORE = JobScore(score=80, tier="tier1", boost=5)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = make_engine(f"sqlite:///{tmp_path / 'nested' / 'jobs.db'}")
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with session_factory(engine)() as s:
        yield s


def test_engine_uses_wal_and_busy_timeout(engine: Engine, tmp_path: Path) -> None:
    assert (tmp_path / "nested" / "jobs.db").exists()
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 30000


def test_upsert_inserts_and_lists_by_score(session: Session) -> None:
    low = repo.upsert_job(session, replace(JOB, company="Initech"), replace(SCORE, score=50))
    high = repo.upsert_job(session, JOB, SCORE)
    session.commit()

    assert high.id.startswith("job_") and len(high.id) == 12
    assert [j.id for j in repo.list_active(session)] == [high.id, low.id]
    assert [j.id for j in repo.list_active(session, min_score=60)] == [high.id]
    stored = repo.get_job(session, high.id)
    assert stored is not None
    assert (stored.score, stored.tier, stored.boost, stored.is_active) == (80, "tier1", 5, True)


def test_upsert_same_content_updates_instead_of_duplicating(session: Session) -> None:
    first = repo.upsert_job(session, JOB, SCORE)
    repo.mark_inactive(session, first.id)
    session.commit()
    assert repo.list_active(session) == []

    seen_again = replace(JOB, title="senior  engineer", url="https://jobs.lever.co/hooli/9")
    again = repo.upsert_job(session, seen_again, replace(SCORE, score=90))
    session.commit()

    assert again.id == first.id
    assert (again.url, again.score, again.is_active) == ("https://jobs.lever.co/hooli/9", 90, True)
    assert again.last_seen_at >= again.discovered_at
    assert len(repo.list_active(session)) == 1


def test_mark_inactive_unknown_job_is_an_error(session: Session) -> None:
    with pytest.raises(KeyError):
        repo.mark_inactive(session, "job_missing")


def test_audit_event_logging(session: Session) -> None:
    repo.record_audit(
        session,
        actor="agent:scout",
        action="JOB_DISCOVERED",
        status="SUCCESS",
        target_id="job_1",
        duration_ms=120,
        details={"source": "greenhouse", "tags": ["a", "b"]},
    )
    repo.record_audit(session, actor="human:user", action="PROFILE_UPDATED", status="WARNING")
    session.commit()

    events = repo.query_audit(session)
    assert [e.action for e in events] == ["PROFILE_UPDATED", "JOB_DISCOVERED"]  # newest first
    scout = repo.query_audit(session, actor="agent:scout")
    assert len(scout) == 1
    assert (scout[0].target_id, scout[0].duration_ms) == ("job_1", 120)
    assert scout[0].details == {"source": "greenhouse", "tags": ["a", "b"]}
    assert len(scout[0].id) == 36
    assert repo.query_audit(session, status="FAILURE") == []
    assert len(repo.query_audit(session, limit=1)) == 1


def test_wal_lets_readers_proceed_during_an_open_write(engine: Engine, tmp_path: Path) -> None:
    other = make_engine(f"sqlite:///{tmp_path / 'nested' / 'jobs.db'}")
    try:
        with session_factory(engine)() as writer, session_factory(other)() as reader:
            repo.upsert_job(writer, JOB, SCORE)
            writer.flush()  # Write transaction open, not committed.
            assert repo.list_active(reader) == []  # Reader is not blocked.
            writer.commit()
            reader.rollback()  # End the old read snapshot.
            assert len(repo.list_active(reader)) == 1
    finally:
        other.dispose()
