import json
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx

from src.ingestion.firecrawl_client import (
    BudgetExceededError,
    FirecrawlClient,
    FirecrawlError,
    SearchResult,
)

SEARCH = "https://api.firecrawl.dev/v2/search"
RESULTS = [
    {
        "url": "https://boards.greenhouse.io/hooli/jobs/1",
        "title": "Senior Engineer",
        "description": "Hooli",
    },
    {"url": "https://jobs.lever.co/initech/abc", "title": "Tech Lead", "description": "Initech"},
]


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 22, 9, 0)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def http() -> Iterator[httpx.Client]:
    with respx.mock, httpx.Client() as c:
        yield c


@pytest.fixture
def clock() -> Clock:
    return Clock()


def _client(http: httpx.Client, tmp_path: Path, clock: Clock, daily: int = 10) -> FirecrawlClient:
    return FirecrawlClient("fc-key", http, tmp_path / "fc", daily_credits=daily, clock=clock)


def _ok(credits: int = 2) -> httpx.Response:
    return httpx.Response(
        200, json={"success": True, "data": {"web": RESULTS}, "creditsUsed": credits}
    )


def test_search_sends_query_and_parses_results(
    http: httpx.Client, tmp_path: Path, clock: Clock
) -> None:
    route = respx.post(SEARCH).mock(return_value=_ok())
    results = _client(http, tmp_path, clock).search(
        '"Tech Lead" site:jobs.lever.co', limit=5, tbs="qdr:w"
    )

    assert results == [SearchResult(**r) for r in RESULTS]
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer fc-key"
    assert json.loads(request.content) == {
        "query": '"Tech Lead" site:jobs.lever.co',
        "limit": 5,
        "tbs": "qdr:w",
    }


def test_results_are_cached_for_12_hours_across_instances(
    http: httpx.Client, tmp_path: Path, clock: Clock
) -> None:
    route = respx.post(SEARCH).mock(return_value=_ok())
    _client(http, tmp_path, clock).search("q")
    clock.now += timedelta(hours=11)
    assert _client(http, tmp_path, clock).search("q") == [SearchResult(**r) for r in RESULTS]
    assert route.call_count == 1

    clock.now += timedelta(hours=2)
    _client(http, tmp_path, clock).search("q")
    assert route.call_count == 2


def test_daily_credit_budget(http: httpx.Client, tmp_path: Path, clock: Clock) -> None:
    route = respx.post(SEARCH).mock(return_value=_ok(credits=4))
    client = _client(http, tmp_path, clock, daily=8)
    client.search("a")
    client.search("b")
    assert client.credits_used_today() == 8

    with pytest.raises(BudgetExceededError):
        client.search("c")
    assert route.call_count == 2  # Refused before calling the API.
    assert client.search("a")  # Cached results are still served for free.

    clock.now += timedelta(days=1)
    assert client.credits_used_today() == 0
    client.search("c")
    assert route.call_count == 3


def test_missing_credits_used_counts_the_limit(
    http: httpx.Client, tmp_path: Path, clock: Clock
) -> None:
    respx.post(SEARCH).respond(200, json={"success": True, "data": {"web": []}})
    client = _client(http, tmp_path, clock)
    client.search("q", limit=3)
    assert client.credits_used_today() == 3


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"success": False, "error": "boom"}),
        httpx.Response(200, json={"success": False, "error": "bad query"}),
    ],
)
def test_api_errors_raise_firecrawl_error(
    http: httpx.Client, tmp_path: Path, clock: Clock, response: httpx.Response
) -> None:
    respx.post(SEARCH).mock(return_value=response)
    with pytest.raises(FirecrawlError):
        _client(http, tmp_path, clock).search("q")


def test_missing_api_key_is_rejected(http: httpx.Client, tmp_path: Path) -> None:
    with pytest.raises(FirecrawlError, match="FIRECRAWL_API_KEY"):
        FirecrawlClient("", http, tmp_path, daily_credits=10)
