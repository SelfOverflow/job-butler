"""Workable public widget API (one request, descriptions included):
apply.workable.com/api/v1/widget/accounts/<board>?details=true."""

from datetime import datetime

import httpx

from src.ingestion.base import RawJobPosting, html_to_markdown
from src.profile.models import WatchedCompany

API = "https://apply.workable.com/api/v1/widget/accounts/{board}"
TIMEOUT = 30.0


def fetch_workable(company: WatchedCompany, client: httpx.Client) -> list[RawJobPosting]:
    response = client.get(
        API.format(board=company.board), params={"details": "true"}, timeout=TIMEOUT
    )
    response.raise_for_status()
    payload = response.json()
    name = payload.get("name") or company.name
    jobs = []
    for job in payload["jobs"]:
        place = ", ".join(p for p in (job.get("city"), job.get("state"), job.get("country")) if p)
        if job.get("telecommuting"):
            place = f"{place}, Remote" if place else "Remote"
        published = job.get("published_on") or job.get("created_at")
        jobs.append(
            RawJobPosting(
                title=job["title"],
                company=name,
                location=place,
                url=job["url"],
                description=html_to_markdown(job.get("description") or ""),
                source="workable",
                posted_at=datetime.fromisoformat(published) if published else None,
            )
        )
    return jobs
