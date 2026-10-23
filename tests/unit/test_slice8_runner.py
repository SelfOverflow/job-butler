from pathlib import Path

import pytest

from src.config.settings import Settings
from src.server.runner import CommandRunner
from src.services.common import CancelToken
from src.storage.database import init_db, make_engine, session_factory
from src.storage.models import CommandStatus

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "Springfield",
    "CANDIDATE_STATE": "State",
    "CANDIDATE_POSTAL_CODE": "00000",
}


@pytest.mark.anyio
async def test_runner_submit_single_flight_and_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    prof = tmp_path / "candidate_profile.yaml"
    prof.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("PROFILE_PATH", str(prof))
    db_path = tmp_path / "jobs.db"
    engine = make_engine(f"sqlite:///{db_path}")
    init_db(engine)
    sessions = session_factory(engine)

    settings = Settings(profile_path=prof, database_url=f"sqlite:///{db_path}")
    runner = CommandRunner(sessions, settings)

    run, created = runner.submit("scout_sweep", {"limit": 5})
    assert created
    assert run.status == CommandStatus.QUEUED

    # Single flight duplicate check
    run_dup, created_dup = runner.submit("scout_sweep", {"limit": 5})
    assert not created_dup
    assert run_dup.id == run.id

    # Cancel while still queued
    assert runner.cancel(run.id)
    await runner.stop()



def test_runner_tailor_one_forwards_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    prof = tmp_path / "candidate_profile.yaml"
    prof.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    settings = Settings(profile_path=prof, database_url=f"sqlite:///{tmp_path / 'jobs.db'}")
    runner = CommandRunner(session_factory(engine), settings)
    seen: dict[str, object] = {}

    def fake_tailor_one(job_id: str, **kwargs: object) -> object:
        seen.update(kwargs)
        raise RuntimeError("stop")

    monkeypatch.setattr("src.server.runner.make_llm", lambda _s: object())
    monkeypatch.setattr("src.server.runner.tailor_service.tailor_one", fake_tailor_one)

    def progress(stage: str, done: int, total: int, detail: str) -> None:
        pass

    with pytest.raises(RuntimeError):
        runner._run_sync("tailor_one", {"job_id": "job_00000001"}, progress, CancelToken())
    assert seen["progress"] is progress
