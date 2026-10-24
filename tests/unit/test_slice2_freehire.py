from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import httpx
import pytest
import respx
import yaml

from src.ingestion.discovery import discover
from src.ingestion.sources.freehire import API, search_freehire
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile

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


def test_freehire_search_parsing(client: httpx.Client) -> None:
    payload = {
        "data": [
            {
                "public_slug": "stripe-senior-full-stack-engineer",
                "title": "Senior Full-Stack Engineer",
                "company": "Stripe",
                "location": "Remote",
                "url": "https://jobs.lever.co/stripe/12345",
                "description": "<p>Build payment infrastructure.</p>",
                "posted_at": "2026-10-20T10:00:00Z",
            }
        ],
        "meta": {"total": 1, "limit": 20, "offset": 0},
    }
    respx.get(API).respond(200, json=payload)

    jobs = search_freehire("Senior Full-Stack Engineer", client, limit=10, days=7)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Senior Full-Stack Engineer"
    assert job.company == "Stripe"
    assert job.location == "Remote"
    assert job.url == "https://jobs.lever.co/stripe/12345"
    assert job.source == "freehire"
    assert "Build payment infrastructure" in job.description
    assert job.posted_at == datetime(2026, 10, 20, 10, 0, 0)


def test_freehire_search_handles_http_errors(client: httpx.Client) -> None:
    respx.get(API).respond(503)
    with pytest.raises(httpx.HTTPError):
        search_freehire("Engineer", client)


def test_discover_integrates_freehire(client: httpx.Client) -> None:
    profile = _profile(
        target_roles=["Fullstack Engineer"],
        watched_companies=[],
        excluded_employers=[],
    )
    freehire_payload = {
        "data": [
            {
                "title": "Fullstack Engineer",
                "company": "Acme",
                "location": "Bengaluru",
                "url": "https://example.com/jobs/1",
                "description": "Python, React",
                "posted_at": "2026-10-22T00:00:00Z",
            }
        ]
    }
    respx.get(API).respond(200, json=freehire_payload)

    jobs, errors = discover(profile, firecrawl=None, http=client, use_freehire=True)
    assert errors == []
    assert any(j.title == "Fullstack Engineer" and j.source == "freehire" for j in jobs)
