from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.profile.loader import ProfileLoader
from src.profile.models import CandidateProfile
from src.scheduler.autopilot import Autopilot, Stage
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}


@pytest.fixture
def loader(tmp_path: Path) -> ProfileLoader:
    path = tmp_path / "profile.yaml"
    path.write_text(TEMPLATE.read_text())
    return ProfileLoader(path, env=ENV)


@pytest.fixture
def sessions(tmp_path: Path) -> Iterator[object]:
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    yield session_factory(engine)
    engine.dispose()


class Recorder:
    def __init__(self, fail: set[str] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail = fail or set()

    def stage(self, name: str) -> Stage:
        def run(profile: CandidateProfile) -> str:
            self.calls.append((name, profile.personal_info.full_name))
            if name in self.fail:
                raise RuntimeError(f"{name} exploded")
            return f"{name} done"

        return Stage(name, run)


def _pilot(
    loader: ProfileLoader, sessions: object, rec: Recorder, sleeps: list[float], **kw: object
) -> Autopilot:
    stages = [rec.stage("sweep"), rec.stage("tailor"), rec.stage("prepare")]
    return Autopilot(loader, sessions, stages, sleep=sleeps.append, rng=lambda: 0.5, **kw)  # type: ignore[arg-type]


def test_autopilot_cycle_orchestration(loader: ProfileLoader, sessions: object) -> None:
    rec, sleeps = Recorder(), []
    report = _pilot(loader, sessions, rec, sleeps).run_cycle()

    assert [name for name, _ in rec.calls] == ["sweep", "tailor", "prepare"]
    assert report.ok and report.results == {
        "sweep": "sweep done",
        "tailor": "tailor done",
        "prepare": "prepare done",
    }
    with sessions() as s:  # type: ignore[operator]
        session: Session = s
        [event] = repo.query_audit(session, action="AUTOPILOT_CYCLE")
        assert (event.actor, event.status) == ("agent:autopilot", "SUCCESS")
        assert event.details["stages"]["tailor"] == "tailor done"


def test_failing_stage_is_isolated(loader: ProfileLoader, sessions: object) -> None:
    rec = Recorder(fail={"tailor"})
    report = _pilot(loader, sessions, rec, []).run_cycle()
    assert [name for name, _ in rec.calls] == ["sweep", "tailor", "prepare"]  # prepare still ran
    assert not report.ok and report.results["tailor"] == "failed: tailor exploded"
    with sessions() as s:  # type: ignore[operator]
        [event] = repo.query_audit(s, action="AUTOPILOT_CYCLE")
        assert event.status == "WARNING"


def test_hot_reload_and_frozen_snapshot(loader: ProfileLoader, sessions: object) -> None:
    rec = Recorder()
    pilot = _pilot(loader, sessions, rec, [])
    pilot.run_cycle()
    loader.path.write_text(loader.path.read_text().replace('"Jane Doe"', '"Jane Q. Doe"'))
    pilot.run_cycle()
    assert {who for _, who in rec.calls[3:]} == {"Jane Q. Doe"}  # picked up the edit next cycle

    loader.path.write_text("personal_info: [broken")  # mid-edit corruption
    report = pilot.run_cycle()
    assert report.ok and {who for _, who in rec.calls[6:]} == {"Jane Q. Doe"}  # last good snapshot
    assert "profile" in report.warnings[0]


def test_no_profile_ever_loaded_fails_the_cycle(tmp_path: Path, sessions: object) -> None:
    rec = Recorder()
    bad = ProfileLoader(tmp_path / "missing.yaml", env=ENV)
    report = _pilot(bad, sessions, rec, []).run_cycle()
    assert not report.ok and rec.calls == [] and "Profile not found" in report.warnings[0]


def test_exponential_backoff_with_jitter(loader: ProfileLoader, sessions: object) -> None:
    rec, sleeps = Recorder(fail={"sweep"}), []
    pilot = _pilot(
        loader, sessions, rec, sleeps, interval_minutes=10, max_backoff_factor=4, jitter=0.1
    )
    pilot.run(max_cycles=4)
    # rng()=0.5 -> jitter 1.0x; failures double the wait up to 4x: 20, 40, 40 min.
    # No sleep follows the last cycle.
    assert sleeps == [1200.0, 2400.0, 2400.0]

    rec.fail.clear()
    sleeps.clear()
    pilot.run(max_cycles=2)
    assert sleeps == [600.0]  # a clean cycle resets to the base interval


def test_jitter_spreads_the_interval(loader: ProfileLoader, sessions: object) -> None:
    sleeps: list[float] = []
    pilot = Autopilot(
        loader,
        sessions,
        [Recorder().stage("sweep")],
        sleep=sleeps.append,
        rng=lambda: 0.0,  # type: ignore[arg-type]
        interval_minutes=10,
        jitter=0.1,
    )
    pilot.run(max_cycles=2)
    assert sleeps == [540.0]  # rng 0.0 -> 0.9x
