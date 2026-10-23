"""LinkedIn public (no-login) job search, used only to discover employers.

The guest pages show whether a job's Apply button leaves LinkedIn
(`public_jobs_apply-link-offsite`) or is Easy Apply (`public_jobs_apply-link-onsite`),
but not the external URL itself, so discovery resolves offsite jobs to the employer's
own ATS board and never stores LinkedIn links. Requests are throttled; a 429 stops
the caller rather than retrying, to stay a light, polite client.
"""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Literal

import httpx

from src.ingestion.base import html_to_text

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; job-butler/0.1)",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 15.0

ApplyType = Literal["offsite", "onsite", "unknown"]

_CARD = re.compile(r'data-entity-urn="urn:li:jobPosting:(\d+)"')
_TITLE = re.compile(r'<h3 class="base-search-card__title">(.*?)</h3>', re.S)
_COMPANY = re.compile(r'<h4 class="base-search-card__subtitle">(.*?)</h4>', re.S)
_LOCATION = re.compile(r'<span class="job-search-card__location">(.*?)</span>', re.S)
_POSTED = re.compile(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})"')


class RateLimitedError(Exception):
    pass


@dataclass(frozen=True)
class LinkedInJob:
    id: str
    title: str
    company: str
    location: str
    posted: date | None


def _field(pattern: re.Pattern[str], chunk: str) -> str:
    match = pattern.search(chunk)
    return html_to_text(match.group(1)) if match else ""


def parse_cards(markup: str) -> list[LinkedInJob]:
    """Job cards from a guest search page; cards missing a title or company are skipped."""
    cards = list(_CARD.finditer(markup))
    ends = [m.start() for m in cards[1:]] + [len(markup)] * bool(cards)
    jobs = []
    for card, end in zip(cards, ends, strict=True):
        job_id, chunk = card.group(1), markup[card.start() : end]
        title, company = _field(_TITLE, chunk), _field(_COMPANY, chunk)
        if title and company:
            posted = _POSTED.search(chunk)
            jobs.append(
                LinkedInJob(
                    job_id,
                    title,
                    company,
                    _field(_LOCATION, chunk),
                    date.fromisoformat(posted.group(1)) if posted else None,
                )
            )
    return jobs


class LinkedInClient:
    def __init__(
        self,
        http: httpx.Client,
        delay: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http, self._delay, self._sleep = http, delay, sleep
        self._first = True

    def _get(self, url: str, params: dict[str, str] | None = None) -> str:
        if not self._first and self._delay:
            self._sleep(self._delay)
        self._first = False
        response = self._http.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        if response.status_code == 429:
            raise RateLimitedError("LinkedIn rate limit reached; stopped early")
        response.raise_for_status()
        return response.text

    def search(self, keywords: str, location: str, max_age_hours: int | None) -> list[LinkedInJob]:
        params = {"keywords": keywords, "location": location, "start": "0"}
        if max_age_hours is not None:
            params["f_TPR"] = f"r{max_age_hours * 3600}"
        return parse_cards(self._get(SEARCH_URL, params))

    def apply_type(self, job_id: str) -> ApplyType:
        page = self._get(DETAIL_URL.format(id=job_id))
        if "public_jobs_apply-link-offsite" in page:
            return "offsite"
        if "public_jobs_apply-link-onsite" in page:
            return "onsite"
        return "unknown"
