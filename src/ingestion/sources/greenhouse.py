"""Greenhouse public job board API: boards-api.greenhouse.io/v1/boards/<board>/jobs."""

from datetime import datetime

import httpx

from src.ingestion.base import RawJobPosting, html_to_markdown, to_naive_utc
from src.profile.models import WatchedCompany

API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
TIMEOUT = 30.0


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


def _parse(value: str | None) -> datetime | None:
    return to_naive_utc(datetime.fromisoformat(value)) if value else None
