from dataclasses import replace

import pytest

from src.ingestion.base import RawJobPosting
from src.ingestion.deduplicator import content_key, dedupe
from src.ingestion.filter import drop_excluded, is_excluded_employer

EXCLUDED = ("Acme Corp", "Globex", "Initech Ltd")


def _job(
    company: str = "Hooli", title: str = "Senior Engineer", location: str = "Remote"
) -> RawJobPosting:
    return RawJobPosting(
        title=title,
        company=company,
        location=location,
        url=f"https://jobs.example.com/{company}/{title}".replace(" ", "-"),
        description="Build things.",
        source="greenhouse",
    )


@pytest.mark.parametrize(
    "company",
    [
        "Acme Corp",
        "ACME CORP",
        "acme corp.",
        "Acme Corp India Pvt. Ltd.",  # alias with legal suffix still excluded
        "Globex",
        "Globex Bank plc",
        "  initech   ltd ",
        "Initech, Ltd",
    ],
)
def test_employer_exclusion_filter(company: str) -> None:
    assert is_excluded_employer(company, EXCLUDED)


@pytest.mark.parametrize("company", ["Acme", "Globexa", "Pineapple Globe", "Hooli", "Initech"])
def test_similar_but_different_employers_are_kept(company: str) -> None:
    assert not is_excluded_employer(company, EXCLUDED)


def test_drop_excluded_keeps_order() -> None:
    jobs = [_job("Hooli"), _job("Globex"), _job("Pied Piper"), _job("acme corp")]
    assert [j.company for j in drop_excluded(jobs, EXCLUDED)] == ["Hooli", "Pied Piper"]


def test_no_exclusions_keeps_everything() -> None:
    jobs = [_job("Globex")]
    assert drop_excluded(jobs, ()) == jobs


def test_content_key_ignores_case_whitespace_and_url() -> None:
    a = _job(title="Senior  Engineer", location="Bengaluru")
    b = replace(a, title="senior engineer", location=" BENGALURU ", url="https://other.example")
    assert content_key(a) == content_key(b)
    assert content_key(a) != content_key(replace(a, location="Pune"))
    assert len(content_key(a)) == 64


def test_dedupe_keeps_first_occurrence() -> None:
    first = _job(company="Hooli")
    dup = replace(first, company="HOOLI", source="firecrawl")
    other = _job(company="Pied Piper")
    assert dedupe([first, dup, other]) == [first, other]
