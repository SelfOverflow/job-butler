"""Collapse the same job seen via several sources (title + company + location)."""

import hashlib
from collections.abc import Iterable

from src.ingestion.base import RawJobPosting, words


def content_key(job: RawJobPosting) -> str:
    parts = (" ".join(words(field)) for field in (job.title, job.company, job.location))
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def dedupe(jobs: Iterable[RawJobPosting]) -> list[RawJobPosting]:
    """Keep the first posting for each content key, preserving order."""
    seen: set[str] = set()
    unique = []
    for job in jobs:
        key = content_key(job)
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique
