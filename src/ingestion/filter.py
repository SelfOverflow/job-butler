"""Hard employer exclusions driven by `preferences.excluded_employers`."""

from collections.abc import Iterable, Sequence

from src.ingestion.base import RawJobPosting, words


def is_excluded_employer(company: str, excluded: Iterable[str]) -> bool:
    """True if any excluded name appears as a whole-word run inside `company`.

    Errs on the side of exclusion: "OakNorth" also matches "OakNorth Bank plc",
    but "Apple" does not match "Pineapple Labs".
    """
    haystack = words(company)
    for name in excluded:
        needle = words(name)
        n = len(needle)
        if n and any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1)):
            return True
    return False


def drop_excluded(jobs: Sequence[RawJobPosting], excluded: Sequence[str]) -> list[RawJobPosting]:
    return [job for job in jobs if not is_excluded_employer(job.company, excluded)]
