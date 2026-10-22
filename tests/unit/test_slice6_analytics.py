from pathlib import Path
from typing import Any

import pytest
import yaml

from src.analytics.market import analyze
from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore, combine, score_job
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}


@pytest.fixture
def profile() -> CandidateProfile:
    raw: dict[str, Any] = interpolate(yaml.safe_load(TEMPLATE.read_text()), ENV)
    return CandidateProfile.model_validate(raw)


def _job(description: str, title: str = "Senior Software Engineer", n: int = 0) -> RawJobPosting:
    return RawJobPosting(title, "Hooli", "Lagos, Nigeria", f"https://x/{n}", description, "x")


def test_combine_matches_score_job(profile: CandidateProfile) -> None:
    job = _job("Python FastAPI PostgreSQL Docker AWS Kubernetes React TypeScript")
    scored = score_job(job, profile)
    assert isinstance(scored, JobScore)
    assert combine(hits=8, seniority=1.0, boost=0) == scored.score == 100


def test_skill_frequency_counter(profile: CandidateProfile) -> None:
    jobs = [
        _job("Python and Kubernetes and Terraform", n=1),
        _job("Python with Kubernetes", n=2),
        _job("Go and Rust", n=3),
        _job("Python", n=4),
    ]
    snapshot = analyze(jobs, profile, threshold=60)
    demand = {d.skill: (d.postings, d.share, d.have) for d in snapshot.demand}
    assert snapshot.total == 4
    assert demand["Python"] == (3, 75.0, True)
    assert demand["Kubernetes"] == (2, 50.0, True)  # template profile lists Kubernetes
    assert demand["Terraform"] == (1, 25.0, False)
    assert [d.skill for d in snapshot.demand][:2] == ["Python", "Kubernetes"]  # most demanded first


def test_upskilling_roi_math(profile: CandidateProfile) -> None:
    # Template skills: Python TypeScript FastAPI React Docker AWS Kubernetes PostgreSQL (8).
    # Title matches a target role (seniority 1.0); 2 of 8 skills -> round(100*(4*0.25+3)/7) = 57.
    # Adding one missing skill mentioned in the JD -> 3/8 -> round(100*(4*0.375+3)/7) = 64 >= 60.
    near = "Python and FastAPI. Terraform and Elixir a plus."
    jobs = [
        _job(near, n=1),
        _job(near.replace("Elixir", "Rust"), n=2),
        _job("Python FastAPI Rust", n=3),
    ]
    snapshot = analyze(jobs, profile, threshold=60)

    assert snapshot.matched == 0
    roi = {u.skill: (u.unlocks, u.demand) for u in snapshot.upskill}
    assert roi["Terraform"] == (2, 2)  # unlocks both postings that mention it
    assert roi["Rust"] == (2, 2)
    assert roi["Elixir"] == (1, 1)
    assert "Kafka" not in roi  # already a verified bullet tag
    assert [u.skill for u in snapshot.upskill][-1] == "Elixir"  # ranked by unlocks, then demand
    assert all(not d.have for d in snapshot.demand if d.skill in roi)


def test_uplift_is_relative_to_current_matches(profile: CandidateProfile) -> None:
    strong = "Python FastAPI PostgreSQL Docker AWS"  # 5/8 -> matched already
    jobs = [_job(strong, n=1), _job("Python and FastAPI. Terraform.", n=2)]
    snapshot = analyze(jobs, profile, threshold=60)
    [terraform] = [u for u in snapshot.upskill if u.skill == "Terraform"]
    assert (snapshot.matched, terraform.unlocks, terraform.uplift_pct) == (1, 1, 100.0)


def test_rejected_postings_are_ignored(profile: CandidateProfile) -> None:
    jobs = [_job("Terraform. 25+ years of experience required.", n=1)]
    assert analyze(jobs, profile, threshold=60).total == 0
