import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from pydantic import ValidationError

from src.ingestion.base import html_to_text
from src.ingestion.sources import fetch_watched
from src.ingestion.sources.greenhouse import fetch_greenhouse
from src.ingestion.sources.lever import fetch_lever
from src.profile.models import WatchedCompany

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/hooli/jobs"
LEVER_API = "https://api.lever.co/v0/postings/hooli"


def _fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    with respx.mock, httpx.Client() as c:
        yield c


def test_watched_company_schema() -> None:
    WatchedCompany(name="Hooli", ats="greenhouse", board="hooli-inc_2")
    with pytest.raises(ValidationError):
        WatchedCompany(name="Hooli", ats="taleo", board="hooli")
    with pytest.raises(ValidationError):
        WatchedCompany(name="Hooli", ats="lever", board="hooli/../x")


def test_html_to_text() -> None:
    escaped = (
        "&lt;h2&gt;About&amp;nbsp;us&lt;/h2&gt;&lt;p&gt;We &lt;b&gt;ship&lt;/b&gt; fast.&lt;/p&gt;"
    )
    assert html_to_text(escaped) == "About us We ship fast."


def test_greenhouse_response_parsing(client: httpx.Client) -> None:
    payload = _fixture("greenhouse_jobs.json")
    route = respx.get(GREENHOUSE_API, params={"content": "true"}).respond(200, json=payload)

    jobs = fetch_greenhouse(WatchedCompany(name="Hooli", ats="greenhouse", board="hooli"), client)

    assert route.called
    assert len(jobs) == len(payload["jobs"])
    first, raw = jobs[0], payload["jobs"][0]
    assert (first.title, first.location, first.url) == (
        raw["title"],
        raw["location"]["name"],
        raw["absolute_url"],
    )
    assert (first.company, first.source) == ("Hooli", "greenhouse")
    assert first.description and "<" not in first.description and "&lt;" not in first.description
    published = datetime.fromisoformat(raw["first_published"])
    assert first.posted_at == published.astimezone(UTC).replace(tzinfo=None)  # naive UTC


def test_lever_response_parsing(client: httpx.Client) -> None:
    payload = _fixture("lever_postings.json")
    respx.get(LEVER_API, params={"mode": "json"}).respond(200, json=payload)

    jobs = fetch_lever(WatchedCompany(name="Hooli", ats="lever", board="hooli"), client)

    assert len(jobs) == len(payload)
    first, raw = jobs[0], payload[0]
    assert (first.title, first.location, first.url) == (
        raw["text"],
        raw["categories"]["location"],
        raw["hostedUrl"],
    )
    assert first.source == "lever"
    assert raw["descriptionPlain"].split()[0] in first.description
    assert raw["lists"][0]["text"] in first.description
    assert "<li>" not in first.description
    assert first.posted_at == datetime.fromtimestamp(raw["createdAt"] / 1000, UTC).replace(
        tzinfo=None
    )


def test_lever_posting_without_location(client: httpx.Client) -> None:
    respx.get(LEVER_API, params={"mode": "json"}).respond(
        200,
        json=[{"text": "Engineer", "hostedUrl": "https://jobs.lever.co/hooli/1", "categories": {}}],
    )
    [job] = fetch_lever(WatchedCompany(name="Hooli", ats="lever", board="hooli"), client)
    assert (job.location, job.description, job.posted_at) == ("", "", None)


def test_fetch_watched_isolates_failing_boards(client: httpx.Client) -> None:
    respx.get(GREENHOUSE_API).respond(200, json=_fixture("greenhouse_jobs.json"))
    respx.get(LEVER_API).respond(503)
    companies = [
        WatchedCompany(name="Hooli", ats="greenhouse", board="hooli"),
        WatchedCompany(name="Hooli Labs", ats="lever", board="hooli"),
    ]

    jobs, errors = fetch_watched(companies, client)

    assert len(jobs) == 2 and all(j.source == "greenhouse" for j in jobs)
    assert len(errors) == 1
    assert errors[0].startswith("Hooli Labs (lever/hooli): ")
    assert "503" in errors[0]
