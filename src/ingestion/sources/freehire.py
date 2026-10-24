"""Freehire public tech jobs API: freehire.me/api/v1/jobs/search."""

from datetime import datetime
from typing import Any

import httpx

from src.ingestion.base import RawJobPosting, html_to_markdown, to_naive_utc

API = "https://freehire.me/api/v1/jobs/search"
HEADERS = {"User-Agent": "job-butler/0.1 (freehire-search)", "Accept": "application/json"}
TIMEOUT = 15.0


def search_freehire(
    query: str,
    client: httpx.Client,
    limit: int = 20,
    days: int | None = None,
) -> list[RawJobPosting]:
    """Search tech jobs via Freehire's public unauthenticated REST API."""
    params: dict[str, str] = {
        "q": query,
        "limit": str(limit),
        "description_format": "markdown",
    }
    if days is not None and days > 0:
        params["posted_within_days"] = str(days)

    response = client.get(API, params=params, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    jobs: list[RawJobPosting] = []
    items: list[dict[str, Any]] = payload.get("data", [])
    for item in items:
        url = item.get("url")
        title = item.get("title")
        if not url or not title:
            continue
        jobs.append(
            RawJobPosting(
                title=title,
                company=item.get("company") or "",
                location=item.get("location") or "",
                url=url,
                description=html_to_markdown(item.get("description") or ""),
                source="freehire",
                posted_at=_parse(item.get("posted_at") or item.get("created_at")),
            )
        )
    return jobs


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return to_naive_utc(datetime.fromisoformat(value))
    except (ValueError, TypeError):
        return None
