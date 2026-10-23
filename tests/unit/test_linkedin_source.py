from collections.abc import Iterator
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from src.ingestion.sources.linkedin import (
    DETAIL_URL,
    SEARCH_URL,
    LinkedInClient,
    RateLimitedError,
    parse_cards,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def http() -> Iterator[httpx.Client]:
    with respx.mock, httpx.Client() as client:
        yield client


def test_parse_cards_from_recorded_search_page() -> None:
    cards = parse_cards(_html("linkedin_search.html"))

    assert len(cards) == 10
    first = cards[0]
    assert (first.id, first.title, first.company) == (
        "4467702783",
        "(Senior) Software Engineer (Fullstack)",
        "4flow",
    )
    assert first.location == "Bengaluru, Karnataka, India"
    assert first.posted == date(2026, 10, 6)
    assert all(c.id.isdigit() and c.title and c.company for c in cards)


def test_search_sends_keywords_location_and_age_window(http: httpx.Client) -> None:
    route = respx.get(SEARCH_URL).respond(200, html=_html("linkedin_search.html"))

    cards = LinkedInClient(http, delay=0).search("Tech Lead", "India", max_age_hours=168)

    assert len(cards) == 10
    params = route.calls.last.request.url.params
    assert (params["keywords"], params["location"], params["f_TPR"]) == (
        "Tech Lead",
        "India",
        "r604800",
    )


def test_apply_type_from_guest_job_page(http: httpx.Client) -> None:
    respx.get(DETAIL_URL.format(id="1")).respond(200, html=_html("linkedin_job_offsite.html"))
    respx.get(DETAIL_URL.format(id="2")).respond(200, html=_html("linkedin_job_onsite.html"))
    respx.get(DETAIL_URL.format(id="3")).respond(200, html="<html>no apply button</html>")
    client = LinkedInClient(http, delay=0)

    assert [client.apply_type(i) for i in ("1", "2", "3")] == ["offsite", "onsite", "unknown"]


def test_requests_are_throttled_and_rate_limits_raise(http: httpx.Client) -> None:
    respx.get(SEARCH_URL).respond(200, html="")
    respx.get(DETAIL_URL.format(id="9")).respond(429)
    pauses: list[float] = []
    client = LinkedInClient(http, delay=1.5, sleep=pauses.append)

    client.search("Tech Lead", "India", max_age_hours=None)
    client.search("Tech Lead", "UK", max_age_hours=None)
    with pytest.raises(RateLimitedError):
        client.apply_type("9")

    assert pauses == [1.5, 1.5]  # Every request after the first waits.
    assert "f_TPR" not in respx.calls[0].request.url.params
