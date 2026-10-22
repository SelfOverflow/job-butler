"""Profile-driven job discovery.

Firecrawl search finds recent postings for each target role on public ATS boards;
every company board found is then pulled in full through its free public API, so
the candidate never has to curate a company list (an explicit
`preferences.watched_companies` list is merged in when present).
"""

import re
from collections.abc import Iterable
from urllib.parse import parse_qs, urlsplit

import httpx

from src.ingestion.base import ProgressFn, RawJobPosting, no_progress
from src.ingestion.filter import is_excluded_employer
from src.ingestion.firecrawl_client import (
    BudgetExceededError,
    FirecrawlClient,
    FirecrawlError,
    SearchResult,
)
from src.ingestion.sources import fetch_watched
from src.profile.models import CandidateProfile, WatchedCompany

SITES = ("boards.greenhouse.io", "job-boards.greenhouse.io", "jobs.lever.co")
RESULTS_PER_QUERY = 10
RECENCY = "qdr:w"  # Postings indexed in the past week.
_SLUG = re.compile(r"^[A-Za-z0-9_-]+$")


def build_queries(profile: CandidateProfile) -> list[str]:
    sites = " OR ".join(f"site:{site}" for site in SITES)
    return [f'"{role}" ({sites})' for role in profile.preferences.target_roles]


def _board_for(url: str) -> WatchedCompany | None:
    parts = urlsplit(url)
    host, segments = parts.hostname or "", [s for s in parts.path.split("/") if s]
    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io"):
        ats, slug = "greenhouse", (parse_qs(parts.query).get("for") or segments or [""])[0]
        if slug == "embed":
            return None
    elif host == "jobs.lever.co" and segments:
        ats, slug = "lever", segments[0]
    else:
        return None
    return WatchedCompany(name=slug, ats=ats, board=slug) if _SLUG.match(slug) else None


def boards_from_results(results: Iterable[SearchResult]) -> list[WatchedCompany]:
    """Unique Greenhouse/Lever boards referenced by search results, in order."""
    boards: dict[tuple[str, str], WatchedCompany] = {}
    for result in results:
        board = _board_for(result.url)
        if board is not None:
            boards.setdefault((board.ats, board.board), board)
    return list(boards.values())


def discover(
    profile: CandidateProfile,
    firecrawl: FirecrawlClient | None,
    http: httpx.Client,
    progress: ProgressFn = no_progress,
) -> tuple[list[RawJobPosting], list[str]]:
    """Search, collect boards, drop excluded employers, and fetch every board."""
    errors: list[str] = []
    results: list[SearchResult] = []
    if firecrawl is not None:
        queries = build_queries(profile)
        progress("search", 0, len(queries), "")
        for done, query in enumerate(queries, start=1):
            try:
                results += firecrawl.search(query, limit=RESULTS_PER_QUERY, tbs=RECENCY)
            except BudgetExceededError as exc:
                errors.append(str(exc))
                progress("search", len(queries), len(queries), "budget exhausted")
                break
            except FirecrawlError as exc:
                errors.append(f"{query}: {exc}")
            progress("search", done, len(queries), query)

    boards: dict[tuple[str, str], WatchedCompany] = {}
    for board in [*profile.preferences.watched_companies, *boards_from_results(results)]:
        boards.setdefault((board.ats, board.board), board)
    excluded = profile.preferences.excluded_employers
    wanted = [b for b in boards.values() if not is_excluded_employer(b.name, excluded)]

    jobs, fetch_errors = fetch_watched(wanted, http, progress)
    return jobs, errors + fetch_errors
