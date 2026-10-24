from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import httpx
import pytest
import respx
import yaml

from src.ingestion.discovery import discover
from src.ingestion.sources.greenhouse import SEARCH_API, search_greenhouse
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile, GreenhouseSearch

ROOT = Path(__file__).resolve().parents[2]
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}


def _profile(**preferences: object) -> CandidateProfile:
    raw = interpolate(
        yaml.safe_load((ROOT / "profile" / "candidate_profile.template.yaml").read_text()), ENV
    )
    raw["preferences"].update(preferences)
    return CandidateProfile.model_validate(raw)


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    with respx.mock, httpx.Client() as c:
        yield c


def test_greenhouse_search_parsing(client: httpx.Client) -> None:
    payload = {
        "data": [
            {
                "public_slug": "anduril-senior-full-stack-engineer",
                "title": "Senior Full-Stack Engineer",
                "company": "Anduril Industries",
                "location": "Costa Mesa, CA",
                "url": "https://boards.greenhouse.io/andurilindustries/jobs/5089044007?gh_jid=5089044007&utm_source=freehire.me",
                "description": "<p>Build defense software.</p>",
                "posted_at": "2026-10-21T10:00:00Z",
            }
        ],
        "meta": {"total": 1, "limit": 20, "offset": 0},
    }
    respx.get(SEARCH_API).respond(200, json=payload)

    jobs = search_greenhouse("Senior Full-Stack Engineer", client, limit=10, days=7)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Senior Full-Stack Engineer"
    assert job.company == "Anduril Industries"
    assert job.location == "Costa Mesa, CA"
    # Tracking params stripped, gh_jid preserved
    assert job.url == "https://boards.greenhouse.io/andurilindustries/jobs/5089044007?gh_jid=5089044007"
    assert job.source == "greenhouse"
    assert "Build defense software" in job.description
    assert job.posted_at == datetime(2026, 10, 21, 10, 0, 0)


def test_greenhouse_search_handles_http_errors(client: httpx.Client) -> None:
    respx.get(SEARCH_API).respond(503)
    with pytest.raises(httpx.HTTPError):
        search_greenhouse("Engineer", client)


def test_greenhouse_profile_preferences_model() -> None:
    search = GreenhouseSearch()
    assert search.enabled is False
    assert search.results_per_role == 15

    custom = GreenhouseSearch(enabled=True, results_per_role=25)
    assert custom.enabled is True
    assert custom.results_per_role == 25


def test_discover_integrates_greenhouse(client: httpx.Client) -> None:
    profile = _profile(
        target_roles=["Fullstack Engineer"],
        watched_companies=[],
        excluded_employers=[],
    )
    greenhouse_search_payload = {
        "data": [
            {
                "title": "Fullstack Engineer",
                "company": "Anduril",
                "location": "Remote",
                "url": "https://boards.greenhouse.io/andurilindustries/jobs/12345",
                "description": "Python, React",
                "posted_at": "2026-10-22T00:00:00Z",
            }
        ]
    }
    board_jobs_payload = {
        "jobs": [
            {
                "id": 12345,
                "title": "Fullstack Engineer",
                "company_name": "Anduril",
                "location": {"name": "Remote"},
                "absolute_url": "https://boards.greenhouse.io/andurilindustries/jobs/12345",
                "content": "<p>Python, React</p>",
                "first_published": "2026-10-22T00:00:00Z",
            }
        ]
    }
    respx.get(SEARCH_API).respond(200, json=greenhouse_search_payload)
    respx.get("https://boards-api.greenhouse.io/v1/boards/andurilindustries/jobs?content=true").respond(
        200, json=board_jobs_payload
    )

    jobs, errors = discover(profile, firecrawl=None, http=client, use_greenhouse=True)
    assert errors == []
    assert any(j.title == "Fullstack Engineer" and j.source == "greenhouse" for j in jobs)

