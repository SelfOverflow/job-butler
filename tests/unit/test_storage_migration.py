from pathlib import Path

from sqlalchemy import inspect, text

from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory
from src.storage.models import JobStatus

JOB = RawJobPosting("Engineer", "Acme", "Remote", "https://example.com/1", "Python", "custom")


def test_new_jobs_default_to_discovered(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    with session_factory(engine)() as session:
        row = repo.upsert_job(session, JOB, JobScore(85, "tier1", 5))
        session.commit()
        assert row.status == JobStatus.DISCOVERED


def test_update_job_status_and_resighting_preserves_it(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    with session_factory(engine)() as session:
        row = repo.upsert_job(session, JOB, JobScore(85, "tier1", 5))
        assert repo.update_job_status(session, row.id, JobStatus.TAILORED) is row
        assert repo.update_job_status(session, "job_missing", JobStatus.TAILORED) is None
        session.commit()
        assert repo.upsert_job(session, JOB, JobScore(90, "tier1", 5)).status == "tailored"


def test_init_db_adds_status_to_legacy_table(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE job_postings (id VARCHAR(16) PRIMARY KEY)"))
        conn.execute(text("INSERT INTO job_postings (id) VALUES ('job_00000001')"))

    init_db(engine)
    init_db(engine)  # Idempotent.

    assert "status" in {c["name"] for c in inspect(engine).get_columns("job_postings")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM job_postings")).scalar() == "discovered"
