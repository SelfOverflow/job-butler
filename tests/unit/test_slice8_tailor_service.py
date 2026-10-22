from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agents.tailor.runner import TailorError
from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.profile.loader import ProfileLoader
from src.services import tailor as tailor_service
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
def profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ProfileLoader:
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    prof_path = tmp_path / "candidate_profile.yaml"
    prof_path.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("PROFILE_PATH", str(prof_path))
    return ProfileLoader(prof_path)


def test_tailor_service_tailor_one_missing_job(profile: ProfileLoader, tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    prof = profile.load()
    with session_factory(engine)() as session:
        with pytest.raises(TailorError, match="No job with id unknown"):
            tailor_service.tailor_one(
                "unknown",
                profile=prof,
                session=session,
                llm=MagicMock(),
                artifacts_dir=tmp_path / "artifacts",
            )


def test_tailor_service_check_pdf(profile: ProfileLoader) -> None:
    prof = profile.load()
    report = tailor_service.check_pdf(b"%PDF-1.4 empty", profile=prof, max_pages=2)
    assert not report.passed
    assert report.pages == 0


def test_tailor_service_matches_cancellation(profile: ProfileLoader, tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    prof = profile.load()
    token = CancelToken()
    token.cancel()
    with session_factory(engine)() as session:
        job = RawJobPosting(
            "Engineer", "Acme", "Remote", "https://example.com/1", "Python", "custom"
        )
        repo.upsert_job(session, job, JobScore(score=85, tier="Tier 1", boost=5))
        session.commit()

        with pytest.raises(CancelledError):
            tailor_service.tailor_matches(
                profile=prof,
                session=session,
                llm=MagicMock(),
                artifacts_dir=tmp_path / "artifacts",
                cancel=token,
            )
