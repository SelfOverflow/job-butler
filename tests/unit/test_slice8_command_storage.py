from pathlib import Path

from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory
from src.storage.models import CommandStatus


def test_command_run_crud(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    with session_factory(engine)() as session:
        run = repo.save_command_run(
            session, "scout_sweep", {"limit": 10}, requested_by="human:user"
        )
        session.commit()
        assert run.id is not None
        assert run.status == CommandStatus.QUEUED
        assert run.command == "scout_sweep"
        assert run.params == {"limit": 10}

        active = repo.find_active_command_run(session, "scout_sweep")
        assert active is not None
        assert active.id == run.id

        repo.start_command_run(session, run.id)
        session.commit()
        fetched = repo.get_command_run(session, run.id)
        assert fetched is not None
        assert fetched.status == CommandStatus.RUNNING
        assert fetched.started_at is not None

        repo.update_command_progress(session, run.id, {"stage": "search", "done": 1, "total": 2})
        session.commit()
        assert fetched.progress == {"stage": "search", "done": 1, "total": 2}

        repo.finish_command_run(
            session, run.id, status=CommandStatus.SUCCEEDED, result={"saved": 5}
        )
        session.commit()
        assert fetched.status == CommandStatus.SUCCEEDED
        assert fetched.result == {"saved": 5}
        assert fetched.finished_at is not None

        # No active run anymore
        assert repo.find_active_command_run(session, "scout_sweep") is None


def test_fail_interrupted_runs(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    with session_factory(engine)() as session:
        r1 = repo.save_command_run(session, "scout_sweep", {})
        r2 = repo.save_command_run(session, "tailor_matches", {})
        repo.start_command_run(session, r1.id)
        session.commit()

        # r1 is running, r2 is queued
        interrupted = repo.fail_interrupted_runs(session)
        session.commit()
        assert interrupted == 1

        f1 = repo.get_command_run(session, r1.id)
        assert f1 is not None
        assert f1.status == CommandStatus.FAILED
        assert "interrupted by restart" in (f1.error or "")

        f2 = repo.get_command_run(session, r2.id)
        assert f2 is not None
        assert f2.status == CommandStatus.QUEUED


def test_fail_interrupted_tailoring(tmp_path: Path) -> None:
    from src.ingestion.base import RawJobPosting
    from src.ingestion.scorer import JobScore
    from src.storage.models import JobStatus

    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    with session_factory(engine)() as session:
        posting = RawJobPosting("Tech Lead", "Hooli", "Remote", "https://x/1", "", "lever")
        row = repo.upsert_job(session, posting, JobScore(90, None, 0))
        row.status = JobStatus.TAILORING  # Server died mid-tailoring.
        session.commit()

        assert repo.fail_interrupted_tailoring(session) == 1
        assert row.status == JobStatus.TAILOR_FAILED
