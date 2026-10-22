from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import classify_tier, score_job, seniority_match, tech_match
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
JD = "We use Python, FastAPI, PostgreSQL, Docker, AWS and Kubernetes. React.js is a plus."


def _profile(needs_visa: bool = True) -> CandidateProfile:
    raw: dict[str, Any] = interpolate(yaml.safe_load(TEMPLATE.read_text()), ENV)
    raw["personal_info"]["work_authorization"]["requires_visa_for_international"] = needs_visa
    return CandidateProfile.model_validate(raw)


def _job(location: str = "San Francisco, CA", description: str = JD) -> RawJobPosting:
    return RawJobPosting(
        title="Senior Software Engineer",
        company="Hooli",
        location=location,
        url="https://jobs.example.com/1",
        description=description,
        source="greenhouse",
    )


@pytest.mark.parametrize(
    ("location", "tier", "boost"),
    [
        ("San Francisco, CA", "tier1_primary_market", 5),
        ("Austin, TX (Hybrid)", "tier1_primary_market", 3),
        ("Berlin, Germany", "tier2_international_priority", 4),
        ("Dubai, UAE", "tier3_secondary_relocation", 2),
        ("Global Remote", "tier4_worldwide", 0),
        ("Lagos, Nigeria", None, 0),
    ],
)
def test_classify_tier(location: str, tier: str | None, boost: int) -> None:
    hierarchy = _profile().preferences.sourcing_hierarchy
    assert classify_tier(location, hierarchy) == (tier, boost)


def test_market_hierarchy_scoring_boost() -> None:
    profile = _profile(needs_visa=False)
    boosted = score_job(_job("New York, NY"), profile)
    unboosted = score_job(_job("Lagos, Nigeria"), profile)
    assert boosted.score - unboosted.score == 5
    assert (boosted.tier, unboosted.tier) == ("tier1_primary_market", None)


@pytest.mark.parametrize(
    "phrase",
    [
        "We are unable to sponsor visas for this role.",
        "No visa sponsorship available.",
        "Open to EU citizens or permanent residents only.",
        "Candidates must have the right to work in Germany; we do not offer sponsorship.",
    ],
)
def test_visa_gate_rejects_foreign_roles_without_sponsorship(phrase: str) -> None:
    result = score_job(_job("Berlin, Germany", f"{JD} {phrase}"), _profile())
    assert result.rejected_reason == "no visa sponsorship"


def test_visa_gate_skips_domestic_roles_and_candidates_without_visa_needs() -> None:
    text = f"{JD} No visa sponsorship available."
    assert score_job(_job("San Francisco, CA", text), _profile()).rejected_reason is None
    # Not a listed hub, but in a citizen country (template: United States) -> still domestic.
    assert score_job(_job("Denver, United States", text), _profile()).rejected_reason is None
    assert score_job(_job("Berlin, Germany", text), _profile(False)).rejected_reason is None
    assert (
        score_job(
            _job("Berlin, Germany", f"{JD} Visa sponsorship provided."), _profile()
        ).rejected_reason
        is None
    )


def test_tech_match_counts_skill_mentions() -> None:
    profile = _profile()
    assert tech_match(JD, profile) == pytest.approx(7 / 8)  # every template skill but TypeScript
    assert tech_match("We love spreadsheets.", profile) == 0
    assert tech_match(JD + " TypeScript", profile) == 1  # saturates at 8 matched skills


def test_tech_match_handles_js_suffix_and_parenthetical_notes() -> None:
    raw: dict[str, Any] = interpolate(yaml.safe_load(TEMPLATE.read_text()), ENV)
    raw["skills_inventory"] = {
        "web": [
            {"name": "React.js", "proficiency": "expert", "years_of_experience": 5},
            {
                "name": "Docker (Multi-stage, hardening)",
                "proficiency": "expert",
                "years_of_experience": 5,
            },
        ]
    }
    profile = CandidateProfile.model_validate(raw)
    assert tech_match("Strong React and Docker skills.", profile) == pytest.approx(2 / 8)
    assert tech_match("Multi-stage builds, hardening.", profile) == 0


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Senior Software Engineer", 1.0),  # exact target role
        ("Tech Lead, Payments", 1.0),
        ("Software Engineer", 2 / 3),
        ("Marketing Manager", 0.0),
    ],
)
def test_seniority_match(title: str, expected: float) -> None:
    assert seniority_match(title, _profile()) == pytest.approx(expected)


def test_score_combines_weights_and_boost() -> None:
    profile = _profile()
    perfect = replace(_job(), description=JD + " TypeScript")
    result = score_job(perfect, profile)
    assert result.score == 100 + 5
    zero = replace(_job("Lagos, Nigeria", "Nothing relevant."), title="Barista")
    assert score_job(zero, profile).score == 0
