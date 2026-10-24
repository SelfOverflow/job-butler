"""Profile-driven job discovery.

Firecrawl search finds recent postings for each target role on public ATS boards;
every company board found is then pulled in full through its free public API, so
the candidate never has to curate a company list (an explicit
`preferences.watched_companies` list is merged in when present).

When `preferences.linkedin` is enabled, LinkedIn also surfaces employers: only jobs
whose Apply button leaves LinkedIn are kept, and each is resolved to the employer's
own Greenhouse/Lever board (verified by a matching title), so stored URLs and posting
dates always come from the employer, never from LinkedIn.
"""

import re
from collections.abc import Iterable, Iterator
from typing import Literal
from urllib.parse import parse_qs, urlsplit

import httpx

from src.ingestion.base import ProgressFn, RawJobPosting, contains_phrase, no_progress, words
from src.ingestion.filter import is_excluded_employer
from src.ingestion.firecrawl_client import (
    BudgetExceededError,
    FirecrawlClient,
    FirecrawlError,
    SearchResult,
)
from src.ingestion.recency import RECENCY_HOURS, search_tbs
from src.ingestion.sources import FETCHERS, fetch_watched
from src.ingestion.sources.freehire import search_freehire
from src.ingestion.sources.greenhouse import search_greenhouse
from src.ingestion.sources.linkedin import LinkedInClient, LinkedInJob, RateLimitedError
from src.profile.models import CandidateProfile, WatchedCompany

AtsName = Literal["greenhouse", "lever", "ashby", "workable"]
ATS_BOARDS: tuple[AtsName, ...] = ("greenhouse", "lever", "ashby", "workable")
SITES = (
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
    "apply.workable.com",
)
RESULTS_PER_QUERY = 10
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
    elif host == "jobs.ashbyhq.com" and segments:
        ats, slug = "ashby", segments[0]
    elif host == "apply.workable.com" and segments and segments[0] not in ("j", "api"):
        ats, slug = "workable", segments[0]
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


def slug_candidates(company: str) -> list[str]:
    """Likely ATS board slugs for a company name, most specific first."""
    name = company.casefold()
    slugs = (
        re.sub(r"[^a-z0-9]", "", name),
        re.sub(r"[^a-z0-9]+", "-", name).strip("-"),
        re.sub(r"[^a-z0-9]", "", name.split()[0]) if name.split() else "",
    )
    return [s for s in dict.fromkeys(slugs) if s]


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def same_company(company: str, board: str) -> bool:
    """True if an ATS board slug plausibly belongs to `company` (e.g. Toast -> toast)."""
    name, slug = _key(company), _key(board)
    if name == slug:
        return bool(name)
    return min(len(name), len(slug)) >= 3 and (slug in name or name in slug)


def _same_role(a: str, b: str) -> bool:
    x, y = words(a), words(b)
    return bool(x and y) and (contains_phrase(x, y) or contains_phrase(y, x))


def _resolve(
    cards: list[LinkedInJob],
    linkedin: LinkedInClient,
    http: httpx.Client,
    firecrawl: FirecrawlClient | None,
) -> tuple[WatchedCompany, list[RawJobPosting]] | None:
    """The employer board listing the first offsite-apply card's role, if any.

    Tries board slugs guessed from the company name, then (if available) a Firecrawl
    search for the role on Greenhouse/Lever. A board only counts if its slug matches the
    company and it lists the role: generic titles appear on many companies' boards.
    """
    card = next((c for c in cards if linkedin.apply_type(c.id) == "offsite"), None)
    if card is None:
        return None
    def candidates() -> Iterator[tuple[AtsName, str]]:
        yield from ((ats, slug) for slug in slug_candidates(card.company) for ats in ATS_BOARDS)
        if firecrawl is not None:  # Only spent when the guesses all miss.
            sites = " OR ".join(f"site:{site}" for site in SITES)
            results = firecrawl.search(f'"{card.title}" "{card.company}" ({sites})', limit=5)
            yield from ((b.ats, b.board) for b in boards_from_results(results))

    for ats, slug in candidates():
        if not same_company(card.company, slug):
            continue
        board = WatchedCompany(name=card.company, ats=ats, board=slug)
        try:
            jobs = FETCHERS[ats](board, http)
        except (httpx.HTTPError, ValueError, KeyError):
            continue
        if any(_same_role(job.title, card.title) for job in jobs):
            return board, jobs
    return None


def linkedin_boards(
    profile: CandidateProfile,
    linkedin: LinkedInClient,
    http: httpx.Client,
    known: set[str],
    progress: ProgressFn = no_progress,
    firecrawl: FirecrawlClient | None = None,
) -> tuple[list[WatchedCompany], list[RawJobPosting], list[str]]:
    """Employer boards (with their postings) found through LinkedIn offsite-apply jobs."""
    prefs, config = profile.preferences, profile.preferences.linkedin
    searches = [(role, place) for role in prefs.target_roles for place in config.locations]
    boards: list[WatchedCompany] = []
    jobs: list[RawJobPosting] = []
    errors: list[str] = []
    by_company: dict[str, list[LinkedInJob]] = {}
    try:
        progress("linkedin", 0, len(searches), "")
        for done, (role, place) in enumerate(searches, start=1):
            try:
                cards = linkedin.search(role, place, RECENCY_HOURS[prefs.job_recency])
            except httpx.HTTPError as exc:
                errors.append(f"LinkedIn {role} in {place}: {exc}")
                cards = []
            for card in cards[: config.results_per_search]:
                key = _key(card.company)
                if key in known or is_excluded_employer(card.company, prefs.excluded_employers):
                    continue
                group = by_company.setdefault(key, [])
                if card.id not in {c.id for c in group}:
                    group.append(card)
            progress("linkedin", done, len(searches), f"{role} in {place}")

        progress("resolve", 0, len(by_company), "")
        for done, cards in enumerate(by_company.values(), start=1):
            try:
                if found := _resolve(cards, linkedin, http, firecrawl):
                    boards.append(found[0])
                    jobs += found[1]
            except BudgetExceededError as exc:
                errors.append(str(exc))
                firecrawl = None  # Keep resolving by slug guesses only.
            except (httpx.HTTPError, FirecrawlError) as exc:
                errors.append(f"LinkedIn {cards[0].company}: {exc}")
            progress("resolve", done, len(by_company), cards[0].company)
    except RateLimitedError as exc:
        errors.append(str(exc))
    return boards, jobs, errors


def discover(
    profile: CandidateProfile,
    firecrawl: FirecrawlClient | None,
    http: httpx.Client,
    progress: ProgressFn = no_progress,
    linkedin: LinkedInClient | None = None,
    use_freehire: bool | None = None,
    use_greenhouse: bool | None = None,
) -> tuple[list[RawJobPosting], list[str]]:
    """Search, collect boards, drop excluded employers, and fetch every board."""
    errors: list[str] = []
    results: list[SearchResult] = []
    if firecrawl is not None:
        queries = build_queries(profile)
        tbs = search_tbs(profile.preferences.job_recency)
        progress("search", 0, len(queries), "")
        for done, query in enumerate(queries, start=1):
            try:
                results += firecrawl.search(query, limit=RESULTS_PER_QUERY, tbs=tbs)
            except BudgetExceededError as exc:
                errors.append(str(exc))
                progress("search", len(queries), len(queries), "budget exhausted")
                break
            except FirecrawlError as exc:
                errors.append(f"{query}: {exc}")
            progress("search", done, len(queries), query)

    freehire_jobs: list[RawJobPosting] = []
    should_freehire = (
        use_freehire
        if use_freehire is not None
        else profile.preferences.freehire.enabled
    )
    if should_freehire:
        prefs = profile.preferences
        hours = RECENCY_HOURS[prefs.job_recency]
        days = max(1, hours // 24) if hours else None
        limit = prefs.freehire.results_per_role
        progress("freehire", 0, len(prefs.target_roles), "")
        for done, role in enumerate(prefs.target_roles, start=1):
            try:
                found = search_freehire(role, http, limit=limit, days=days)
                freehire_jobs.extend(found)
            except httpx.HTTPError as exc:
                errors.append(f"Freehire {role}: {exc}")
            progress("freehire", done, len(prefs.target_roles), role)

    freehire_boards = boards_from_results(
        [
            SearchResult(url=j.url, title=j.title, description=j.description)
            for j in freehire_jobs
        ]
    )

    greenhouse_jobs: list[RawJobPosting] = []
    should_greenhouse = (
        use_greenhouse
        if use_greenhouse is not None
        else profile.preferences.greenhouse.enabled
    )
    if should_greenhouse:
        prefs = profile.preferences
        hours = RECENCY_HOURS[prefs.job_recency]
        days = max(1, hours // 24) if hours else None
        limit = prefs.greenhouse.results_per_role
        progress("greenhouse", 0, len(prefs.target_roles), "")
        for done, role in enumerate(prefs.target_roles, start=1):
            try:
                found = search_greenhouse(role, http, limit=limit, days=days)
                greenhouse_jobs.extend(found)
            except httpx.HTTPError as exc:
                errors.append(f"Greenhouse {role}: {exc}")
            progress("greenhouse", done, len(prefs.target_roles), role)

    greenhouse_boards = boards_from_results(
        [
            SearchResult(url=j.url, title=j.title, description=j.description)
            for j in greenhouse_jobs
        ]
    )

    boards: dict[tuple[str, str], WatchedCompany] = {}
    for board in [
        *profile.preferences.watched_companies,
        *boards_from_results(results),
        *freehire_boards,
        *greenhouse_boards,
    ]:
        boards.setdefault((board.ats, board.board), board)
    excluded = profile.preferences.excluded_employers
    wanted = [b for b in boards.values() if not is_excluded_employer(b.name, excluded)]

    linkedin_jobs: list[RawJobPosting] = []
    if profile.preferences.linkedin.enabled:
        known = {_key(b.name) for b in wanted} | {_key(b.board) for b in wanted}
        # Resolved boards arrive with their postings, so they are not fetched again.
        _, linkedin_jobs, linkedin_errors = linkedin_boards(
            profile, linkedin or LinkedInClient(http), http, known, progress, firecrawl
        )
        errors += linkedin_errors

    # Watched career portals come first so they win on duplicates, then searched boards.
    jobs, fetch_errors = fetch_watched(wanted, http, progress)
    return jobs + linkedin_jobs + freehire_jobs + greenhouse_jobs, errors + fetch_errors
