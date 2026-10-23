import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from src.ingestion.discovery import boards_from_results
from src.ingestion.firecrawl_client import SearchResult
from src.ingestion.sources import FETCHERS
from src.ingestion.sources.ashby import fetch_ashby
from src.ingestion.sources.workable import fetch_workable
from src.profile.models import WatchedCompany

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def http() -> Iterator[httpx.Client]:
    with respx.mock, httpx.Client() as client:
        yield client


def test_ashby_board_parsing(http: httpx.Client) -> None:
    payload = _fixture("ashby_jobs.json")
    payload["jobs"].append({**payload["jobs"][0], "id": "x", "isListed": False})
    respx.get("https://api.ashbyhq.com/posting-api/job-board/linear").respond(200, json=payload)

    jobs = fetch_ashby(WatchedCompany(name="Linear", ats="ashby", board="linear"), http)

    assert len(jobs) == 2  # Unlisted postings are skipped.
    first, raw = jobs[0], payload["jobs"][0]
    assert (first.title, first.company, first.url, first.source) == (
        raw["title"],
        "Linear",
        raw["jobUrl"],
        "ashby",
    )
    assert first.location.startswith("Europe") and "Remote" in first.location
    assert first.posted_at == datetime(2021, 4, 27, 20, 13, 45, 158000)
    assert first.description.startswith("At Linear") and "<p" not in first.description


def test_workable_board_parsing(http: httpx.Client) -> None:
    payload = _fixture("workable_jobs.json")
    route = respx.get("https://apply.workable.com/api/v1/widget/accounts/careers").respond(
        200, json=payload
    )

    [job] = fetch_workable(WatchedCompany(name="x", ats="workable", board="careers"), http)

    assert route.calls.last.request.url.params["details"] == "true"
    raw = payload["jobs"][0]
    assert (job.title, job.company, job.url, job.source) == (
        raw["title"],
        "Workable",  # The board's own company name wins.
        raw["url"],
        "workable",
    )
    assert job.location == "Athens, Greece"
    assert job.posted_at == datetime(2026, 10, 6)
    assert job.description and "<p>" not in job.description


def test_new_ats_are_registered_and_discoverable() -> None:
    assert {"greenhouse", "lever", "ashby", "workable"} <= set(FETCHERS)
    results = [
        SearchResult("https://jobs.ashbyhq.com/linear/d3bc1ced", "t", "d"),
        SearchResult("https://apply.workable.com/careers/j/94F9E30E22/", "t", "d"),
        SearchResult("https://apply.workable.com/j/94F9E30E22", "t", "d"),  # No board slug.
    ]
    assert [(b.ats, b.board) for b in boards_from_results(results)] == [
        ("ashby", "linear"),
        ("workable", "careers"),
    ]
