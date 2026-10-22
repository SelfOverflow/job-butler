"""Job recency: how fresh a posting must be to be discovered and saved.

`preferences.job_recency` drives both the Firecrawl search window (`tbs`) and a
filter on each posting's published date. Postings with no published date are
kept: there is no evidence they are stale.
"""

from datetime import date, datetime, timedelta

from src.profile.models import Recency
from src.storage.models import utcnow

RECENCY_HOURS: dict[Recency, int | None] = {
    "24h": 24,
    "48h": 48,
    "72h": 72,
    "1w": 168,
    "2w": 336,
    "1m": 720,
    "any": None,
}
_NATIVE_WINDOWS: dict[Recency, str] = {"24h": "qdr:d", "1w": "qdr:w", "1m": "qdr:m"}


def search_tbs(recency: Recency, today: date | None = None) -> str | None:
    """Search time filter: native past-day/week/month windows, else an explicit date range."""
    hours = RECENCY_HOURS[recency]
    if hours is None:
        return None
    if recency in _NATIVE_WINDOWS:
        return _NATIVE_WINDOWS[recency]
    today = today or date.today()
    start = today - timedelta(days=hours // 24)
    return f"cdr:1,cd_min:{start:%m/%d/%Y},cd_max:{today:%m/%d/%Y}"


def is_recent(posted_at: datetime | None, recency: Recency, now: datetime | None = None) -> bool:
    hours = RECENCY_HOURS[recency]
    if posted_at is None or hours is None:
        return True
    return posted_at >= (now or utcnow()) - timedelta(hours=hours)
