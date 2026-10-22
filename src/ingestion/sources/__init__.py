"""Direct ATS board adapters for `preferences.watched_companies`."""

from collections.abc import Callable, Sequence

import httpx

from src.ingestion.base import RawJobPosting
from src.ingestion.sources.greenhouse import fetch_greenhouse
from src.ingestion.sources.lever import fetch_lever
from src.profile.models import WatchedCompany

FETCHERS: dict[str, Callable[[WatchedCompany, httpx.Client], list[RawJobPosting]]] = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
}


def fetch_watched(
    companies: Sequence[WatchedCompany], client: httpx.Client
) -> tuple[list[RawJobPosting], list[str]]:
    """Fetch every watched board; one failing board never aborts the sweep.

    Returns (postings, error messages) so callers can audit-log the failures.
    """
    jobs: list[RawJobPosting] = []
    errors: list[str] = []
    for company in companies:
        try:
            jobs += FETCHERS[company.ats](company, client)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            errors.append(f"{company.name} ({company.ats}/{company.board}): {exc}")
    return jobs, errors
