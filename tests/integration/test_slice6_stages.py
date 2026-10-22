from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from sqlalchemy.orm import Session, sessionmaker

from src.agents.llm import LLMClient, LLMError
from src.agents.tailor.runner import artifact_paths
from src.config.settings import Settings
from src.ingestion.base import RawJobPosting
from src.ingestion.pipeline import SweepReport
from src.ingestion.scorer import JobScore
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile
from src.scheduler.autopilot import Stage
from src.scheduler.stages import AutopilotLimits, build_stages
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory
from src.storage.models import ApplicationStatus

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}


@pytest.fixture
def profile() -> CandidateProfile:
    raw: dict[str, Any] = interpolate(yaml.safe_load(TEMPLATE.read_text()), ENV)
    return CandidateProfile.model_validate(raw)


@pytest.fixture
def db(tmp_path: Path) -> Iterator[tuple[sessionmaker[Session], Settings, dict[int, str]]]:
    url = f"sqlite:///{tmp_path / 'jobs.db'}"
    engine = make_engine(url)
    init_db(engine)
    sessions = session_factory(engine)
    ids = {}
    with sessions() as session:
        for score in (95, 90, 85, 80, 60):
            job = RawJobPosting(
                f"Role {score}", "Hooli", "Remote", f"https://x/{score}", "Python", "lever"
            )
            ids[score] = repo.upsert_job(session, job, JobScore(score, None, 0)).id
        session.commit()
    yield (
        sessions,
        Settings(_env_file=None, database_url=url, artifacts_dir=tmp_path / "artifacts"),
        ids,
    )
    engine.dispose()


def _tailored(settings: Settings, job_id: str) -> None:
    path = artifact_paths(settings.artifacts_dir, job_id).resume
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF")


def _stage(stages: list[Stage], name: str) -> Stage:
    return next(s for s in stages if s.name == name)


def test_tailor_stage_picks_best_untailored_jobs_above_min_score(
    db: tuple[sessionmaker[Session], Settings, dict[int, str]],
    profile: CandidateProfile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions, settings, ids = db
    _tailored(settings, ids[95])
    tailored: list[str] = []
    monkeypatch.setattr("src.scheduler.stages.tailor_job", lambda row, *_a: tailored.append(row.id))
    stages = build_stages(
        settings,
        sessions,
        AutopilotLimits(tailor_per_cycle=2, min_score=82),
        llm_factory=lambda _s: cast(LLMClient, object()),
    )

    summary = _stage(stages, "tailor").run(profile)

    assert tailored == [ids[90], ids[85]]  # 95 already tailored; 80 and 60 below min score
    assert summary == "tailored 2, failed 0"


def test_tailor_stage_is_skipped_without_an_llm_key(
    db: tuple[sessionmaker[Session], Settings, dict[int, str]], profile: CandidateProfile
) -> None:
    sessions, settings, _ = db

    def no_key(_settings: Settings) -> object:
        raise LLMError("GEMINI_API_KEY is not set")

    stages = build_stages(settings, sessions, AutopilotLimits(), llm_factory=no_key)  # type: ignore[arg-type]
    assert _stage(stages, "tailor").run(profile) == "skipped: GEMINI_API_KEY is not set"


def test_prepare_stage_only_prepares_tailored_jobs_without_an_application(
    db: tuple[sessionmaker[Session], Settings, dict[int, str]],
    profile: CandidateProfile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions, settings, ids = db
    for score in (95, 90, 85):
        _tailored(settings, ids[score])
    with sessions() as session:
        repo.save_application(session, ids[95], status=ApplicationStatus.SUBMITTED)
        session.commit()

    def fake_prepare(job_id: str, *, session: Session, **_kw: object) -> object:
        return repo.save_application(session, job_id, status=ApplicationStatus.AWAITING_REVIEW)

    monkeypatch.setattr("src.scheduler.stages.prepare", fake_prepare)
    stages = build_stages(settings, sessions, AutopilotLimits(prepare_per_cycle=5, min_score=50))
    assert _stage(stages, "prepare").run(profile) == "prepared 2: 2 awaiting review"


def test_sweep_stage_summarises_the_report(
    db: tuple[sessionmaker[Session], Settings, dict[int, str]],
    profile: CandidateProfile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions, settings, _ = db
    report = SweepReport(
        discovered=412, rejected=40, stale=12, saved=19, new=7, market_postings=360
    )
    monkeypatch.setattr("src.scheduler.stages.run_sweep", lambda *_a, **_k: report)
    summary = _stage(build_stages(settings, sessions, AutopilotLimits()), "sweep").run(profile)
    assert summary == "discovered 412, rejected 40, stale 12, saved 19 (7 new), market 360"
