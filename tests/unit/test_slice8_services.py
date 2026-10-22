from pathlib import Path

import pytest

from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.profile.loader import ProfileError, ProfileLoader
from src.profile.updater import ProfileUpdater
from src.services import profile as profile_service
from src.services import scout as scout_service
from src.services.common import CancelledError, CancelToken
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "Springfield",
    "CANDIDATE_STATE": "State",
    "CANDIDATE_POSTAL_CODE": "00000",
}


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    prof_path = tmp_path / "candidate_profile.yaml"
    monkeypatch.setenv("PROFILE_PATH", str(prof_path))
    return prof_path


def test_cancel_token() -> None:
    token = CancelToken()
    assert not token.is_cancelled
    token.check()
    token.cancel()
    assert token.is_cancelled
    with pytest.raises(CancelledError):
        token.check()


def test_profile_service_init_and_validate(env: Path) -> None:
    target = profile_service.init_profile(TEMPLATE, env)
    assert target.exists()

    with pytest.raises(ProfileError, match="already exists"):
        profile_service.init_profile(TEMPLATE, env, force=False)

    summary = profile_service.validate_profile(ProfileLoader(env))
    assert summary.full_name == "Jane Doe"
    assert summary.bullet_count == 3
    assert summary.role_count == 2
    assert summary.star_story_count == 1
    assert summary.screening_count == 5


def test_profile_service_query_and_export(env: Path, tmp_path: Path) -> None:
    profile_service.init_profile(TEMPLATE, env)
    profile = ProfileLoader(env).load()

    question = "Are you legally authorized to work in the United States?"
    val = profile_service.query_screening(profile, question)
    assert val is True

    with pytest.raises(ProfileError, match="No matching screening answer"):
        profile_service.query_screening(profile, "What is your favorite color?")

    target = tmp_path / "master.md"
    out = profile_service.export_master(profile, target)
    assert out == target
    assert "# Jane Doe" in target.read_text(encoding="utf-8")


def test_profile_service_update_and_backups(env: Path) -> None:
    profile_service.init_profile(TEMPLATE, env)
    loader = ProfileLoader(env)
    updater = ProfileUpdater(loader, env.parent / "backups")

    pairs = profile_service.update_profile(updater, ["preferences.currency=EUR"])
    assert pairs == [("preferences.currency", "EUR")]
    assert loader.load().preferences.currency == "EUR"

    bullet_id = profile_service.add_bullet(
        updater, "exp_company_alpha", "Wrote high-throughput service", ["Go", "Kafka"]
    )
    assert bullet_id.startswith("b_")

    backups = profile_service.list_backups(updater)
    assert len(backups) >= 2

    restored = profile_service.restore_backup(updater, backups[0].name)
    assert restored == env


def test_scout_service(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    with session_factory(engine)() as session:
        job = RawJobPosting(
            "Engineer", "Acme", "Remote", "https://example.com/1", "Python", "custom"
        )
        score = JobScore(score=85, tier="Tier 1", boost=5)
        repo.upsert_job(session, job, score)
        session.commit()

        jobs = scout_service.list_jobs(session)
        assert len(jobs) == 1
        assert jobs[0].company == "Acme"
