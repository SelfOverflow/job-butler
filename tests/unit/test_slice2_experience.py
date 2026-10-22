from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.ingestion.base import RawJobPosting
from src.ingestion.experience import required_years, total_experience_years
from src.ingestion.scorer import score_job
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}


def _raw() -> dict[str, Any]:
    raw: dict[str, Any] = interpolate(yaml.safe_load(TEMPLATE.read_text()), ENV)
    return raw


def _role(start: str, end: str | None, i: int) -> dict[str, Any]:
    return {
        "id": f"exp_{i}",
        "company": f"Co {i}",
        "title": "Engineer",
        "start_date": start,
        "end_date": end,
        "is_current": end is None,
        "atomic_bullets": [{"id": f"b_{i}", "text": f"Did thing {i}."}],
    }


def _profile(roles: list[tuple[str, str | None]] | None = None, **prefs: Any) -> CandidateProfile:
    raw = _raw()
    if roles is not None:
        raw["work_experience"] = [_role(s, e, i) for i, (s, e) in enumerate(roles)]
    raw["preferences"].update(prefs)
    return CandidateProfile.model_validate(raw)


@pytest.mark.parametrize(
    ("text", "years"),
    [
        ("5+ years of experience building backend systems.", 5),
        ("Requires 7-10 years of professional software experience.", 7),
        ("7–10 yrs experience in distributed systems", 7),
        ("A minimum of 8 years' experience is required.", 8),
        ("At least five years of relevant experience.", 5),
        ("Experience: 6+ years", 6),
        ("Minimum experience of 4 years in React Native.", 4),
        ("3+ years with React and 8+ years of backend experience.", 8),  # highest wins
        ("0-2 years of experience welcome", 0),
        ("10 or more years of hands-on engineering experience", 10),
        # Real phrasings without the word "experience":
        ("Required Qualifications: 6-8+ years building full-stack products, including", 6),
        ("What you'll bring to the role 9+ years in Python and its libraries", 9),
        ("6+ years with modern front-end frameworks (e.g., React)", 6),
        ("Minimum 7 years as a software engineer.", 7),
        ("You bring 4 years.", 4),
    ],
)
def test_required_years_parsing(text: str, years: int) -> None:
    assert required_years(text) == years


@pytest.mark.parametrize(
    "text",
    [
        "We were founded 12 years ago and ship fast.",
        "Python, React, and AWS. Strong communication skills.",
        "Candidates must be at least 18 years of age.",
        "Offering a 2 year contract with relocation support.",
        "We grew revenue 3x in 2 years.",
        "Our 20-year history in fintech.",
    ],
)
def test_text_without_experience_requirement(text: str) -> None:
    assert required_years(text) is None


def test_total_experience_merges_overlaps_and_counts_current_role() -> None:
    profile = _profile(
        roles=[
            ("2020-03", "2020-05"),  # 2 months
            ("2021-07", "2024-04"),  # overlaps the next role by 0 months
            ("2024-04", "2025-07"),
            ("2025-01", "2025-06"),  # fully inside the previous role
            ("2025-07", None),  # current
        ]
    )
    years = total_experience_years(profile, today=date(2026, 10, 22))
    assert years == pytest.approx((2 + 63) / 12, abs=0.01)  # Mar-May 2020 + Jul 2021-Oct 2026


def test_explicit_years_override_wins() -> None:
    profile = _profile(years_of_experience=3.5)
    assert total_experience_years(profile, today=date(2030, 1, 1)) == 3.5


def _job(description: str) -> RawJobPosting:
    return RawJobPosting(
        "Senior Software Engineer", "Hooli", "San Francisco, CA", "u", description, "x"
    )


def test_roles_requiring_more_experience_are_rejected() -> None:
    profile = _profile(years_of_experience=5.4)
    result = score_job(_job("Python and AWS. 8+ years of experience required."), profile)
    assert result.rejected_reason == "experience: requires 8+ years, profile has 5.4"


@pytest.mark.parametrize(
    "description", ["5+ years of experience.", "3-5 years experience.", "Python and AWS."]
)
def test_roles_within_experience_are_kept(description: str) -> None:
    profile = _profile(years_of_experience=5.4)
    assert score_job(_job(description), profile).rejected_reason is None


def test_experience_gate_applies_to_domestic_and_international_roles() -> None:
    profile = _profile(years_of_experience=2)
    domestic = _job("4+ years of experience.")
    abroad = RawJobPosting(
        "Engineer", "Hooli", "Berlin, Germany", "u", "4+ years of experience.", "x"
    )
    assert score_job(domestic, profile).rejected_reason is not None
    assert score_job(abroad, profile).rejected_reason is not None
