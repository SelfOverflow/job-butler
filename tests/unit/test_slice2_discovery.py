import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
import yaml

from src.ingestion.discovery import boards_from_results, build_queries, discover
from src.ingestion.firecrawl_client import FirecrawlClient, SearchResult
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile, WatchedCompany

ROOT = Path(__file__).resolve().parents[2]
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
SEARCH = "https://api.firecrawl.dev/v2/search"
GREENHOUSE_JOBS = json.loads((ROOT / "tests" / "fixtures" / "greenhouse_jobs.json").read_text())


def _profile(**preferences: Any) -> CandidateProfile:
    raw: dict[str, Any] = interpolate(
        yaml.safe_load((ROOT / "profile" / "candidate_profile.template.yaml").read_text()), ENV
    )
    raw["preferences"].update(preferences)
    return CandidateProfile.model_validate(raw)


def _result(url: str) -> SearchResult:
    return SearchResult(url=url, title="t", description="d")


@pytest.fixture
def http() -> Iterator[httpx.Client]:
    with respx.mock, httpx.Client() as c:
        yield c


def test_build_queries_cover_every_target_role() -> None:
    profile = _profile()
    queries = build_queries(profile)
    assert len(queries) == len(profile.preferences.target_roles)
    for role, query in zip(profile.preferences.target_roles, queries, strict=True):
        assert query.startswith(f'"{role}" (')
        assert "site:jobs.lever.co" in query and "site:boards.greenhouse.io" in query


def test_boards_from_results() -> None:
    results = [
        _result("https://boards.greenhouse.io/hooli/jobs/123"),
        _result("https://job-boards.greenhouse.io/hooli/jobs/456"),  # same board
        _result("https://boards.greenhouse.io/embed/job_app?for=pied-piper&token=9"),
        _result("https://jobs.lever.co/initech/abc-def"),
        _result("https://jobs.ashbyhq.com/globex/1"),
        _result("https://example.com/careers/1"),
        _result("https://jobs.lever.co/bad%20slug/1"),
    ]
    assert boards_from_results(results) == [
        WatchedCompany(name="hooli", ats="greenhouse", board="hooli"),
        WatchedCompany(name="pied-piper", ats="greenhouse", board="pied-piper"),
        WatchedCompany(name="initech", ats="lever", board="initech"),
        WatchedCompany(name="globex", ats="ashby", board="globex"),
    ]


def test_discover_merges_search_and_watchlist_and_skips_excluded(
    http: httpx.Client, tmp_path: Path
) -> None:
    profile = _profile(
        excluded_employers=["Initech"],
        watched_companies=[{"name": "Pied Piper", "ats": "greenhouse", "board": "piedpiper"}],
    )
    web = [
        {"url": "https://boards.greenhouse.io/hooli/jobs/1"},
        {"url": "https://jobs.lever.co/initech/x"},
    ]
    respx.post(SEARCH).respond(200, json={"success": True, "data": {"web": web}, "creditsUsed": 1})
    hooli = respx.get("https://boards-api.greenhouse.io/v1/boards/hooli/jobs").respond(
        200, json=GREENHOUSE_JOBS
    )
    piper = respx.get("https://boards-api.greenhouse.io/v1/boards/piedpiper/jobs").respond(
        200, json={"jobs": []}
    )
    initech = respx.get("https://api.lever.co/v0/postings/initech")

    firecrawl = FirecrawlClient("fc-key", http, tmp_path, daily_credits=100)
    jobs, errors = discover(profile, firecrawl, http)

    assert errors == []
    assert hooli.called and piper.called and not initech.called
    assert len(jobs) == len(GREENHOUSE_JOBS["jobs"])
    assert {j.company for j in jobs} == {GREENHOUSE_JOBS["jobs"][0]["company_name"]}


def test_discover_without_firecrawl_uses_watchlist_only(http: httpx.Client) -> None:
    profile = _profile(watched_companies=[{"name": "Hooli", "ats": "greenhouse", "board": "hooli"}])
    respx.get("https://boards-api.greenhouse.io/v1/boards/hooli/jobs").respond(
        200, json=GREENHOUSE_JOBS
    )
    jobs, errors = discover(profile, None, http)
    assert len(jobs) == len(GREENHOUSE_JOBS["jobs"]) and errors == []


def test_discover_stops_searching_when_budget_runs_out(http: httpx.Client, tmp_path: Path) -> None:
    web = [{"url": "https://boards.greenhouse.io/hooli/jobs/1"}]
    search = respx.post(SEARCH).respond(
        200, json={"success": True, "data": {"web": web}, "creditsUsed": 5}
    )
    respx.get("https://boards-api.greenhouse.io/v1/boards/hooli/jobs").respond(
        200, json=GREENHOUSE_JOBS
    )

    firecrawl = FirecrawlClient("fc-key", http, tmp_path, daily_credits=5)
    jobs, errors = discover(_profile(), firecrawl, http)

    assert search.call_count == 1  # Remaining role queries skipped once the budget is spent.
    assert len(jobs) == len(GREENHOUSE_JOBS["jobs"])  # Boards found so far are still fetched.
    assert len(errors) == 1 and "budget" in errors[0]


def test_discover_reports_search_progress(http: httpx.Client, tmp_path: Path) -> None:
    respx.post(SEARCH).respond(200, json={"success": True, "data": {"web": []}, "creditsUsed": 1})
    events: list[tuple[str, int, int, str]] = []
    profile = _profile()
    discover(profile, FirecrawlClient("k", http, tmp_path, 100), http, lambda *e: events.append(e))
    n = len(profile.preferences.target_roles)
    searches = [(d, t) for s, d, t, _ in events if s == "search"]
    assert searches == [(i, n) for i in range(n + 1)]


def test_discover_uses_the_profile_recency(http: httpx.Client, tmp_path: Path) -> None:
    route = respx.post(SEARCH).respond(
        200, json={"success": True, "data": {"web": []}, "creditsUsed": 1}
    )
    discover(_profile(job_recency="24h"), FirecrawlClient("k", http, tmp_path, 100), http)
    assert json.loads(route.calls.last.request.content)["tbs"] == "qdr:d"
    discover(_profile(job_recency="any"), FirecrawlClient("k", http, tmp_path / "2", 100), http)
    assert "tbs" not in json.loads(route.calls.last.request.content)
