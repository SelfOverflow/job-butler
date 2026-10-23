import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
import yaml

from src.ingestion.discovery import discover, same_company, slug_candidates
from src.ingestion.firecrawl_client import FirecrawlClient
from src.ingestion.sources.linkedin import DETAIL_URL, SEARCH_URL, LinkedInClient
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile

ROOT = Path(__file__).resolve().parents[2]
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
BOARD = "https://boards-api.greenhouse.io/v1/boards/{}/jobs"
HOOLI = json.loads((ROOT / "tests" / "fixtures" / "greenhouse_jobs.json").read_text())
ACME = {
    "jobs": [
        {
            "title": "Tech Lead (Platform)",
            "location": {"name": "Bengaluru, India"},
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
            "content": "&lt;p&gt;Python&lt;/p&gt;",
            "first_published": "2026-09-01T00:00:00Z",
        }
    ]
}


def _profile(**preferences: Any) -> CandidateProfile:
    raw: dict[str, Any] = interpolate(
        yaml.safe_load((ROOT / "profile" / "candidate_profile.template.yaml").read_text()), ENV
    )
    raw["preferences"].update(
        target_roles=["Tech Lead"],
        excluded_employers=["Globex"],
        watched_companies=[{"name": "Hooli", "ats": "greenhouse", "board": "hooli"}],
        **preferences,
    )
    return CandidateProfile.model_validate(raw)


def _card(job_id: str, company: str) -> str:
    return (
        f'<li><div data-entity-urn="urn:li:jobPosting:{job_id}">'
        '<h3 class="base-search-card__title">Tech Lead - Platform</h3>'
        f'<h4 class="base-search-card__subtitle"><a href="#">{company}</a></h4>'
        '<span class="job-search-card__location">India</span>'
        '<time datetime="2026-10-20"></time></div></li>'
    )


@pytest.fixture
def http() -> Iterator[httpx.Client]:
    with respx.mock, httpx.Client() as client:
        respx.get(BOARD.format("hooli")).respond(200, json=HOOLI)
        yield client


def test_slug_candidates() -> None:
    assert slug_candidates("Acme Corp.") == ["acmecorp", "acme-corp", "acme"]
    assert slug_candidates("4flow") == ["4flow"]


def test_same_company() -> None:
    assert same_company("Sony Interactive Entertainment", "sonyinteractiveentertainmentglobal")
    assert same_company("U.S. Bank", "usbank") and same_company("Toast", "toast")
    assert not same_company("U.S. Bank", "us")  # Too short to be evidence.
    assert not same_company("U.S. Bank", "adyen")


def test_linkedin_offsite_jobs_resolve_to_employer_boards(http: httpx.Client) -> None:
    cards = [("1", "Acme"), ("2", "Easy Co"), ("3", "Nowhere"), ("4", "Globex"), ("5", "Hooli")]
    search = respx.get(SEARCH_URL).respond(200, html="".join(_card(*c) for c in cards))
    offsite = '<a data-tracking-control-name="public_jobs_apply-link-offsite_sign-in">Apply</a>'
    onsite = '<a data-tracking-control-name="public_jobs_apply-link-onsite">Apply</a>'
    details = {i: respx.get(DETAIL_URL.format(id=i)).respond(200, html=offsite) for i in "1345"}
    details["2"] = respx.get(DETAIL_URL.format(id="2")).respond(200, html=onsite)
    acme = respx.get(BOARD.format("acme")).respond(200, json=ACME)
    respx.route(host="boards-api.greenhouse.io").respond(404)
    for host in ("api.lever.co", "api.ashbyhq.com", "apply.workable.com"):
        respx.route(host=host).respond(404)
    stages: list[str] = []

    profile = _profile(linkedin={"enabled": True, "locations": ["India"]})
    jobs, errors = discover(
        profile, None, http, lambda s, *_: stages.append(s), LinkedInClient(http, delay=0)
    )

    assert errors == []
    assert search.call_count == 1 and search.calls.last.request.url.params["location"] == "India"
    assert not details["4"].called and not details["5"].called  # Excluded / already known.
    assert acme.call_count == 1  # Resolved board is not fetched a second time.
    found = [j for j in jobs if j.company == "Acme"]
    assert [(j.url, j.source) for j in found] == [
        ("https://boards.greenhouse.io/acme/jobs/1", "greenhouse")
    ]
    assert not any("linkedin.com" in j.url for j in jobs)
    assert {"linkedin", "resolve", "boards"} <= set(stages)


def test_unguessable_boards_fall_back_to_firecrawl(http: httpx.Client, tmp_path: Path) -> None:
    respx.get(SEARCH_URL).respond(200, html=_card("1", "Nowhere Labs"))
    respx.get(DETAIL_URL.format(id="1")).respond(200, html="public_jobs_apply-link-offsite")
    def firecrawl_search(request: httpx.Request) -> httpx.Response:
        fallback = "Nowhere Labs" in json.loads(request.content)["query"]
        web = [
            {"url": "https://job-boards.greenhouse.io/adyen/jobs/3"},  # Same title, other company.
            {"url": "https://job-boards.greenhouse.io/nowherelabs-india/jobs/7"},
        ] * fallback
        return httpx.Response(200, json={"success": True, "data": {"web": web}, "creditsUsed": 1})

    search = respx.post("https://api.firecrawl.dev/v2/search").mock(side_effect=firecrawl_search)
    adyen = respx.get(BOARD.format("adyen")).respond(200, json=ACME)
    respx.get(BOARD.format("nowherelabs-india")).respond(200, json=ACME)
    respx.route(host="boards-api.greenhouse.io").respond(404)
    for host in ("api.lever.co", "api.ashbyhq.com", "apply.workable.com"):
        respx.route(host=host).respond(404)

    profile = _profile(linkedin={"enabled": True, "locations": ["India"]})
    firecrawl = FirecrawlClient("fc-key", http, tmp_path, daily_credits=100)
    jobs, errors = discover(profile, firecrawl, http, linkedin=LinkedInClient(http, delay=0))

    assert errors == []
    query = json.loads(search.calls.last.request.content)["query"]
    assert query.startswith('"Tech Lead - Platform" "Nowhere Labs" (site:')
    assert not adyen.called  # A board must belong to the LinkedIn employer, not just list the role.
    assert [(j.company, j.url) for j in jobs if "acme" in j.url] == [
        ("Nowhere Labs", "https://boards.greenhouse.io/acme/jobs/1")
    ]


def test_linkedin_rate_limit_keeps_other_sources(http: httpx.Client) -> None:
    respx.get(SEARCH_URL).respond(429)
    profile = _profile(linkedin={"enabled": True, "locations": ["India", "UK"]})

    jobs, errors = discover(profile, None, http, linkedin=LinkedInClient(http, delay=0))

    assert errors == ["LinkedIn rate limit reached; stopped early"]
    assert len(jobs) == len(HOOLI["jobs"])


def test_linkedin_is_off_by_default(http: httpx.Client) -> None:
    jobs, errors = discover(_profile(), None, http)
    assert errors == [] and len(jobs) == len(HOOLI["jobs"])  # No LinkedIn route was hit.
