"""Hard employer exclusions driven by `preferences.excluded_employers`."""

from collections.abc import Iterable, Sequence

from src.ingestion.base import RawJobPosting, contains_phrase, words


def is_excluded_employer(company: str, excluded: Iterable[str]) -> bool:
    """True if any excluded name appears as a whole-word run inside `company`.

    Errs on the side of exclusion: "OakNorth" also matches "OakNorth Bank plc",
    but "Apple" does not match "Pineapple Labs".
    """
    haystack = words(company)
    return any(contains_phrase(haystack, words(name)) for name in excluded)


def drop_excluded(jobs: Sequence[RawJobPosting], excluded: Sequence[str]) -> list[RawJobPosting]:
    return [job for job in jobs if not is_excluded_employer(job.company, excluded)]
