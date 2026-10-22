"""Market demand and upskilling ROI, computed with the real fit scorer.

Only postings passing every hard gate are counted. A posting is "matched" when
its fit score reaches `threshold`. For each technology the candidate lacks, ROI
is the number of postings mentioning it that would cross the threshold if it
were added to the profile (one more tech hit, all else equal).
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from src.analytics.skills import candidate_skills, mentioned_skills
from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import combine, score_job, seniority_match, tech_hits
from src.profile.models import CandidateProfile

DEFAULT_THRESHOLD = 60


@dataclass(frozen=True)
class Demand:
    skill: str
    postings: int
    share: float  # Percent of analysed postings mentioning the skill.
    have: bool


@dataclass(frozen=True)
class Upskill:
    skill: str
    unlocks: int  # Postings that would newly reach the threshold.
    demand: int  # Postings mentioning the skill at all.
    uplift_pct: float  # Unlocks relative to currently matched postings.


@dataclass
class MarketSnapshot:
    total: int = 0
    matched: int = 0
    threshold: int = DEFAULT_THRESHOLD
    demand: list[Demand] = field(default_factory=list)
    upskill: list[Upskill] = field(default_factory=list)


def analyze(
    postings: Iterable[RawJobPosting], profile: CandidateProfile, threshold: int = DEFAULT_THRESHOLD
) -> MarketSnapshot:
    have = candidate_skills(profile)
    mentions: Counter[str] = Counter()
    unlocks: Counter[str] = Counter()
    total = matched = 0
    for job in postings:
        scored = score_job(job, profile)
        if scored.rejected_reason:
            continue
        total += 1
        skills = mentioned_skills(job.description)
        mentions.update(skills)
        if scored.score >= threshold:
            matched += 1
            continue
        boosted = combine(
            tech_hits(job.description, profile) + 1,
            seniority_match(job.title, profile),
            scored.boost,
        )
        if boosted >= threshold:
            unlocks.update(skills - have)

    def pct(n: int, of: int) -> float:
        return round(100 * n / of, 1) if of else 0.0

    demand = [Demand(s, n, pct(n, total), s in have) for s, n in mentions.most_common()]
    ranked = sorted(unlocks.items(), key=lambda item: (-item[1], -mentions[item[0]], item[0]))
    upskill = [Upskill(s, n, mentions[s], pct(n, matched or n)) for s, n in ranked]
    return MarketSnapshot(total, matched, threshold, demand, upskill)
