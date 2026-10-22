from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
import yaml
from sqlalchemy.orm import Session

from src.ingestion.pipeline import prune_ineligible, run_sweep, verify_stored
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory

ROOT = Path(__file__).resolve().parents[2]
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
BOARD = "https://boards-api.greenhouse.io/v1/boards/{}/jobs"
JD = "Python, FastAPI, PostgreSQL, Docker, AWS, Kubernetes, React and TypeScript."


def _gh_job(
    n: int, title: str, location: str, content: str = JD, company: str = "Hooli"
) -> dict[str, Any]:
    return {
        "title": title,
        "location": {"name": location},
        "absolute_url": f"https://boards.greenhouse.io/hooli/jobs/{n}",
        "content": content,
        "company_name": company,
    }


GOOD = _gh_job(1, "Senior Software Engineer", "San Francisco, CA")
OKAY = _gh_job(2, "Software Engineer", "Austin, TX", content="Python.")
NO_VISA = _gh_job(3, "Tech Lead", "Berlin, Germany", content=f"{JD} No visa sponsorship.")
CLOSED = _gh_job(4, "Tech Lead", "New York, NY")
EXCLUDED = _gh_job(5, "Tech Lead", "Remote", company="Globex Corp")


def _profile() -> CandidateProfile:
    raw: dict[str, Any] = interpolate(
        yaml.safe_load((ROOT / "profile" / "candidate_profile.template.yaml").read_text()), ENV
    )
    raw["personal_info"]["work_authorization"]["requires_visa_for_international"] = True
    raw["preferences"]["excluded_employers"] = ["Globex"]
    raw["preferences"]["watched_companies"] = [
        {"name": "Hooli", "ats": "greenhouse", "board": "hooli"},
        {"name": "Hooli EU", "ats": "greenhouse", "board": "hooli-eu"},
    ]
    return CandidateProfile.model_validate(raw)


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    with session_factory(engine)() as s:
        yield s
    engine.dispose()


@pytest.fixture
def http() -> Iterator[httpx.Client]:
    with respx.mock, httpx.Client() as c:
        respx.get(BOARD.format("hooli")).respond(
            200, json={"jobs": [GOOD, OKAY, NO_VISA, CLOSED, EXCLUDED]}
        )
        respx.get(BOARD.format("hooli-eu")).respond(200, json={"jobs": [GOOD]})  # duplicate
        for job in (GOOD, OKAY, NO_VISA, EXCLUDED):
            respx.get(job["absolute_url"]).respond(200, html="<h1>Apply now</h1>")
        respx.get(CLOSED["absolute_url"]).respond(404)
        yield c


def test_run_sweep_filters_scores_verifies_and_saves(session: Session, http: httpx.Client) -> None:
    report = run_sweep(_profile(), session, http, firecrawl=None)

    assert (report.discovered, report.excluded, report.duplicates) == (6, 1, 1)
    assert (report.rejected, report.closed, report.saved, report.new) == (1, 1, 2, 2)
    assert report.rejected_by == {"visa": 1} and report.pruned == 0
    saved = repo.list_active(session)
    assert [j.title for j in saved] == ["Senior Software Engineer", "Software Engineer"]
    assert all(j.last_verified_at is not None for j in saved)

    discovered = repo.query_audit(session, action="JOB_DISCOVERED")
    assert sorted(e.target_id or "" for e in discovered) == sorted(j.id for j in saved)
    [sweep] = repo.query_audit(session, action="SCOUT_SWEEP")
    assert (sweep.actor, sweep.status, sweep.details["saved"]) == ("agent:scout", "SUCCESS", 2)
    assert sweep.duration_ms is not None


def test_run_sweep_limit_verifies_only_top_scored(session: Session, http: httpx.Client) -> None:
    report = run_sweep(_profile(), session, http, firecrawl=None, limit=1)
    assert report.saved == 1
    assert [j.title for j in repo.list_active(session)] == ["Senior Software Engineer"]


def test_rerun_is_idempotent(session: Session, http: httpx.Client) -> None:
    run_sweep(_profile(), session, http, firecrawl=None)
    report = run_sweep(_profile(), session, http, firecrawl=None)
    assert (report.saved, report.new) == (2, 0)
    assert len(repo.list_active(session)) == 2
    assert len(repo.query_audit(session, action="JOB_DISCOVERED")) == 2


def test_discovery_errors_mark_sweep_as_warning(session: Session, http: httpx.Client) -> None:
    respx.get(BOARD.format("hooli-eu")).respond(503)
    report = run_sweep(_profile(), session, http, firecrawl=None)
    assert len(report.errors) == 1
    [sweep] = repo.query_audit(session, action="SCOUT_SWEEP")
    assert sweep.status == "WARNING" and sweep.details["errors"] == report.errors


def test_verify_stored_deactivates_closed_jobs(session: Session, http: httpx.Client) -> None:
    run_sweep(_profile(), session, http, firecrawl=None)
    respx.get(GOOD["absolute_url"]).respond(200, html="This position has been filled.")
    respx.get(OKAY["absolute_url"]).respond(503)

    counts = verify_stored(session, http)

    assert counts == {"live": 0, "closed": 1, "unknown": 1}
    assert [j.title for j in repo.list_active(session)] == ["Software Engineer"]  # unknown kept
    statuses = {
        e.details["liveness"]: e.status for e in repo.query_audit(session, action="LINK_VERIFIED")
    }
    assert statuses == {"closed": "WARNING", "unknown": "WARNING"}


def test_progress_events_cover_each_stage(session: Session, http: httpx.Client) -> None:
    events: list[tuple[str, int, int, str]] = []
    run_sweep(_profile(), session, http, firecrawl=None, progress=lambda *e: events.append(e))

    boards = [e for e in events if e[0] == "boards"]
    assert [(done, total) for _, done, total, _ in boards] == [(0, 2), (1, 2), (2, 2)]
    assert boards[1][3] == "Hooli"
    verifies = [e for e in events if e[0] == "verify"]
    assert [(done, total) for _, done, total, _ in verifies] == [(0, 3), (1, 3), (2, 3), (3, 3)]
    assert verifies[1][3] == GOOD["absolute_url"]
    assert not [e for e in events if e[0] == "search"]  # no Firecrawl client

    events.clear()
    verify_stored(session, http, progress=lambda *e: events.append(e))
    assert [(s, d, t) for s, d, t, _ in events] == [
        ("verify", 0, 2),
        ("verify", 1, 2),
        ("verify", 2, 2),
    ]


TOO_SENIOR = _gh_job(
    6, "Principal Engineer", "San Francisco, CA", content=f"{JD} 25+ years of experience."
)


def test_sweep_rejects_roles_requiring_more_experience(
    session: Session, http: httpx.Client
) -> None:
    respx.get(BOARD.format("hooli")).respond(200, json={"jobs": [GOOD, TOO_SENIOR]})
    report = run_sweep(_profile(), session, http, firecrawl=None)
    assert report.rejected_by == {"experience": 1}
    assert [j.title for j in repo.list_active(session)] == ["Senior Software Engineer"]


def test_stored_ineligible_jobs_are_pruned(session: Session, http: httpx.Client) -> None:
    from src.ingestion.base import RawJobPosting
    from src.ingestion.scorer import JobScore

    stale = RawJobPosting(
        "Principal Engineer",
        "Initech",
        "Remote",
        "https://x/9",
        "25+ years of experience.",
        "lever",
    )
    row = repo.upsert_job(session, stale, JobScore(90, None, 0))  # saved before the gate existed
    session.commit()

    assert prune_ineligible(session, _profile()) == 1
    session.commit()
    assert repo.get_job(session, row.id).is_active is False  # type: ignore[union-attr]
    [event] = repo.query_audit(session, action="JOB_EXCLUDED")
    assert event.target_id == row.id and event.details["reason"].startswith(
        "experience: requires 25+"
    )

    repo.upsert_job(session, stale, JobScore(90, None, 0))  # re-activated by a stale writer
    session.commit()
    report = run_sweep(_profile(), session, http, firecrawl=None)
    assert report.pruned == 1 and repo.get_job(session, row.id).is_active is False  # type: ignore[union-attr]


def test_prune_also_refreshes_scores_of_kept_jobs(session: Session) -> None:
    from src.ingestion.base import RawJobPosting
    from src.ingestion.scorer import JobScore, score_job

    job = RawJobPosting(
        "Senior Software Engineer", "Hooli", "San Francisco, CA", "https://x/7", JD, "lever"
    )
    row = repo.upsert_job(
        session, job, JobScore(1, None, 0)
    )  # stale score/tier from an old profile
    session.commit()

    assert prune_ineligible(session, _profile()) == 0
    fresh = score_job(job, _profile())
    assert (row.score, row.tier, row.boost) == (fresh.score, fresh.tier, fresh.boost)
    assert row.tier == "tier1_primary_market"
