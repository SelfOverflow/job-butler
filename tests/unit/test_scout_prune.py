from pathlib import Path

import pytest

from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.profile.loader import ProfileLoader
from src.services import scout as scout_service
from src.services.scout import ScoutError
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory
from src.storage.models import JobStatus

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
GOOD = RawJobPosting("Tech Lead", "Hooli", "Remote", "https://x/1", "Python", "lever")
INTERN = RawJobPosting("SWE Intern", "Hooli", "Remote", "https://x/2", "Python", "lever")


def test_prune_one_is_sticky_and_audited(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    with session_factory(engine)() as session:
        row = repo.upsert_job(session, GOOD, JobScore(90, None, 0))
        session.commit()

        assert scout_service.prune_one(session, row.id) is row
        assert (row.is_active, row.status) == (False, JobStatus.PRUNED)
        [event] = repo.query_audit(session, action="JOB_EXCLUDED")
        assert (event.actor, event.target_id) == ("human:user", row.id)
        assert event.details["reason"] == "manual: pruned by user"

        repo.upsert_job(session, GOOD, JobScore(95, None, 0))  # Re-sighted by a later sweep.
        assert row.is_active is False and row.status == JobStatus.PRUNED

        with pytest.raises(ScoutError, match="Job not found"):
            scout_service.prune_one(session, "job_missing")


def test_prune_all_applies_profile_gates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "profile.yaml").write_text(TEMPLATE.read_text())
    profile = ProfileLoader(tmp_path / "profile.yaml").load()
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    with session_factory(engine)() as session:
        repo.upsert_job(session, GOOD, JobScore(90, None, 0))
        intern = repo.upsert_job(session, INTERN, JobScore(90, None, 0))
        session.commit()

        assert scout_service.prune(session, profile) == 1
        assert intern.is_active is False
