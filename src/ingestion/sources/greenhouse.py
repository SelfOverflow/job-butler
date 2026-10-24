"""Greenhouse public job board API and global ATS search."""

from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from src.ingestion.base import RawJobPosting, html_to_markdown, to_naive_utc
from src.profile.models import WatchedCompany

API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
SEARCH_API = "https://freehire.me/api/v1/jobs/search"
HEADERS = {"User-Agent": "job-butler/0.1 (greenhouse-discovery)", "Accept": "application/json"}
TIMEOUT = 30.0


def _clean_greenhouse_url(url: str) -> str:
    """Strip tracking query parameters while preserving structural ones (e.g. gh_jid)."""
    parts = urlsplit(url)
    query_params = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.startswith("utm_")
    ]
    query_str = urlencode(query_params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query_str, parts.fragment))


def fetch_greenhouse(company: WatchedCompany, client: httpx.Client) -> list[RawJobPosting]:
    response = client.get(
        API.format(board=company.board), params={"content": "true"}, timeout=TIMEOUT
    )
    response.raise_for_status()
    return [
        RawJobPosting(
            title=job["title"],
            company=job.get("company_name") or company.name,
            location=(job.get("location") or {}).get("name", ""),
            url=job["absolute_url"],
            description=html_to_markdown(job.get("content", "")),
            source="greenhouse",
            posted_at=_parse(job.get("first_published") or job.get("updated_at")),
        )
        for job in response.json()["jobs"]
    ]


def search_greenhouse(
    query: str,
    client: httpx.Client,
    limit: int = 20,
    days: int | None = None,
) -> list[RawJobPosting]:
    """Search global Greenhouse-hosted jobs across all firms via public ATS index."""
    params: dict[str, str] = {
        "q": query,
        "source": "greenhouse",
        "limit": str(limit),
        "description_format": "markdown",
    }
    if days is not None and days > 0:
        params["posted_within_days"] = str(days)

    response = client.get(SEARCH_API, params=params, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    jobs: list[RawJobPosting] = []
    items: list[dict[str, Any]] = payload.get("data", [])
    for item in items:
        raw_url = item.get("url")
        title = item.get("title")
        if not raw_url or not title:
            continue
        clean_url = _clean_greenhouse_url(raw_url)
        jobs.append(
            RawJobPosting(
                title=title,
                company=item.get("company") or "",
                location=item.get("location") or "",
                url=clean_url,
                description=html_to_markdown(item.get("description") or ""),
                source="greenhouse",
                posted_at=_parse(item.get("posted_at") or item.get("created_at")),
            )
        )
    return jobs


def _parse(value: str | None) -> datetime | None:
    return to_naive_utc(datetime.fromisoformat(value)) if value else None
