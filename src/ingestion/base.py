"""Source-agnostic job posting DTO shared by every ingestion adapter."""

import re
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RawJobPosting:
    title: str
    company: str
    location: str
    url: str
    description: str
    source: str  # Adapter name, e.g. "greenhouse", "lever", "firecrawl".
    posted_at: datetime | None = None


def words(text: str) -> tuple[str, ...]:
    """Case- and punctuation-insensitive word tuple: `"Acme, Corp."` -> `("acme", "corp")`."""
    return tuple(re.sub(r"[^\w]+", " ", text.casefold()).split())


def contains_phrase(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    """True if `needle` occurs as a contiguous run of whole words in `haystack`."""
    n = len(needle)
    return n > 0 and any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))
