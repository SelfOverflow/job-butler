"""Ashby public job board API: api.ashbyhq.com/posting-api/job-board/<board>."""

from datetime import datetime

import httpx

from src.ingestion.base import RawJobPosting, html_to_markdown, to_naive_utc
from src.profile.models import WatchedCompany

API = "https://api.ashbyhq.com/posting-api/job-board/{board}"
TIMEOUT = 30.0


def fetch_ashby(company: WatchedCompany, client: httpx.Client) -> list[RawJobPosting]:
    response = client.get(API.format(board=company.board), timeout=TIMEOUT)
    response.raise_for_status()
    jobs = []
    for job in response.json()["jobs"]:
        if not job.get("isListed", True):
            continue
        places = [job.get("location") or ""]
        places += [s.get("location", "") for s in job.get("secondaryLocations") or []]
        if job.get("isRemote"):
            places.append("Remote")
        published = job.get("publishedAt")
        jobs.append(
            RawJobPosting(
                title=job["title"],
                company=company.name,
                location=", ".join(p for p in dict.fromkeys(places) if p),
                url=job["jobUrl"],
                description=html_to_markdown(job.get("descriptionHtml") or ""),
                source="ashby",
                posted_at=to_naive_utc(datetime.fromisoformat(published)) if published else None,
            )
        )
    return jobs
