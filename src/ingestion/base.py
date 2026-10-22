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
