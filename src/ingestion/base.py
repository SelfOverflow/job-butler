"""Source-agnostic job posting DTO shared by every ingestion adapter."""

import html
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

# progress(stage, done, total, detail): called with done=0 when a stage starts and
# after each completed step, so callers can render progress without coupling.
ProgressFn = Callable[[str, int, int, str], None]


def no_progress(stage: str, done: int, total: int, detail: str) -> None:
    pass


@dataclass(frozen=True)
class RawJobPosting:
    title: str
    company: str
    location: str
    url: str
    description: str
    source: str  # Adapter name, e.g. "greenhouse", "lever", "firecrawl".
    posted_at: datetime | None = None

    def __post_init__(self) -> None:
        # Sources are sloppy ("GovTech "); trimming keeps dedupe keys and display clean.
        for name in ("title", "company", "location"):
            object.__setattr__(self, name, getattr(self, name).strip())


def words(text: str) -> tuple[str, ...]:
    """Case- and punctuation-insensitive word tuple: `"Acme, Corp."` -> `("acme", "corp")`."""
    return tuple(re.sub(r"[^\w]+", " ", text.casefold()).split())


def contains_phrase(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    """True if `needle` occurs as a contiguous run of whole words in `haystack`."""
    n = len(needle)
    if n == 0:
        return False
    if n == 1:
        return needle[0] in haystack  # C-level scan; this is the hot path in scoring.
    start = 0
    while True:  # Only compare at positions where the first word occurs.
        try:
            i = haystack.index(needle[0], start)
        except ValueError:
            return False
        if haystack[i : i + n] == needle:
            return True
        start = i + 1


def html_to_text(markup: str) -> str:
    """Plain text from (possibly entity-escaped) HTML, whitespace collapsed."""
    stripped = re.sub(r"<[^>]+>", " ", html.unescape(markup))
    return " ".join(html.unescape(stripped).split())


def to_naive_utc(moment: datetime) -> datetime:
    """Storage uses naive UTC; aware datetimes are converted, naive ones assumed UTC."""
    return moment.astimezone(UTC).replace(tzinfo=None) if moment.tzinfo else moment
