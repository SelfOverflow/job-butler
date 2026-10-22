"""Fit score: tech stack + seniority (4:3, scaled to 100) plus the market tier boost.

A role is domestic if it falls in the first `sourcing_hierarchy` tier or a tier
marked `domestic: true`, or names one of the candidate's citizen countries. Other
roles are rejected when they rule out visa sponsorship and the candidate needs a
visa abroad.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from src.ingestion.base import RawJobPosting, contains_phrase, words
from src.ingestion.experience import required_years, total_experience_years
from src.profile.models import CandidateProfile, MarketTier

TECH_SATURATION = 8  # Matched skills needed for full tech marks.
TECH_WEIGHT, SENIORITY_WEIGHT = 4, 3  # Spec's 40% / 30%, rescaled to 100.

_NO_SPONSORSHIP = re.compile(
    r"\bno (visa )?sponsorship\b"
    r"|\b(unable|not able) to (offer |provide )?(visa )?sponsor"
    r"|\b(cannot|can't|can not|will not|won't|do not|don't|does not) "
    r"(offer |provide )?(visa )?sponsor"
    r"|\b(citizens?|nationals?)( (or|and|/) (permanent residents?|pr))? only\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class JobScore:
    score: int
    tier: str | None
    boost: int
    rejected_reason: str | None = None


def classify_tier(location: str, hierarchy: Mapping[str, MarketTier]) -> tuple[str | None, int]:
    """Tier whose most specific (longest) place name appears in `location`, with its boost.

    Longest match wins so "Global Remote" beats a bare "Remote" hub; ties go to the
    earlier (higher-priority) tier.
    """
    haystack = words(location)
    best: tuple[int, str | None, int] = (0, None, 0)
    for name, tier in hierarchy.items():
        for places, boost in (
            (tier.hubs, tier.boost),
            (tier.standard_hubs, tier.standard_boost),
            (tier.countries + tier.locations, tier.boost),
        ):
            for place in places:
                needle = words(place)
                if len(needle) > best[0] and contains_phrase(haystack, needle):
                    best = (len(needle), name, boost)
    return best[1], best[2]


def skill_variants(name: str) -> list[tuple[str, ...]]:
    base = words(name.split("(")[0])  # "Docker (Multi-stage)" -> ("docker",)
    if len(base) > 1 and base[-1] == "js":  # "React.js" also matches "React"
        return [base, base[:-1]]
    return [base]


def tech_match(description: str, profile: CandidateProfile) -> float:
    text = words(description)
    skills = [s for group in profile.skills_inventory.values() for s in group]
    hits = sum(any(contains_phrase(text, v) for v in skill_variants(s.name)) for s in skills)
    return min(hits, TECH_SATURATION) / TECH_SATURATION


def seniority_match(title: str, profile: CandidateProfile) -> float:
    """Best share of a target role's words present in the job title."""
    title_words = set(words(title))
    targets = [set(words(role)) for role in profile.preferences.target_roles]
    return max((len(t & title_words) / len(t) for t in targets if t), default=0.0)


def is_domestic(location: str, profile: CandidateProfile) -> bool:
    """First tier, a tier marked `domestic`, or a location naming a citizen country."""
    hierarchy = profile.preferences.sourcing_hierarchy
    tier, _ = classify_tier(location, hierarchy)
    countries = profile.personal_info.work_authorization.citizen_countries
    return (
        tier == next(iter(hierarchy))
        or (tier is not None and hierarchy[tier].domestic)
        or any(contains_phrase(words(location), words(c)) for c in countries)
    )


def score_job(job: RawJobPosting, profile: CandidateProfile) -> JobScore:
    tier, boost = classify_tier(job.location, profile.preferences.sourcing_hierarchy)
    needed, have = required_years(job.description), total_experience_years(profile)
    if needed is not None and needed > have:
        reason = f"experience: requires {needed}+ years, profile has {have:.1f}"
        return JobScore(score=0, tier=tier, boost=boost, rejected_reason=reason)
    needs_visa = profile.personal_info.work_authorization.requires_visa_for_international
    if (
        needs_visa
        and not is_domestic(job.location, profile)
        and _NO_SPONSORSHIP.search(job.description)
    ):
        return JobScore(
            score=0, tier=tier, boost=boost, rejected_reason="visa: no sponsorship offered"
        )

    fit = (
        TECH_WEIGHT * tech_match(job.description, profile)
        + SENIORITY_WEIGHT * seniority_match(job.title, profile)
    ) / (TECH_WEIGHT + SENIORITY_WEIGHT)
    return JobScore(score=round(100 * fit) + boost, tier=tier, boost=boost)
