from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import BaseModel

from src.agents.tailor.drafter import DraftPlan, TailoredResume, review
from src.agents.tailor.summary import SummaryDraft, grounding_problems, tailor_summary
from src.ingestion.base import RawJobPosting
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile
from tests.fakes import FakeLLM

ROOT = Path(__file__).resolve().parents[2]
ENV = {
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
JD = "Senior Backend Engineer. You will build Python and Kafka services. 8+ years. Golang a plus."
JOB = RawJobPosting("Senior Backend Engineer", "Hooli", "San Francisco, CA", "u", JD, "greenhouse")
GOOD = (
    "Senior Backend Engineer who architected an event-driven ingestion pipeline handling "
    "25,000 requests per second with 99.99% uptime, and reduced database latency by 45% "
    "with distributed Redis caching."
)


@pytest.fixture
def profile() -> CandidateProfile:
    raw: dict[str, Any] = interpolate(
        yaml.safe_load((ROOT / "profile" / "candidate_profile.template.yaml").read_text()), ENV
    )
    return CandidateProfile.model_validate(raw)


@pytest.fixture
def resume(profile: CandidateProfile) -> TailoredResume:
    ids = [b.id for b in profile.bullets]
    return review(DraftPlan(keywords=["Python"], bullet_ids=ids), JOB, profile)


def _llm(*texts: str) -> FakeLLM:
    queue = list(texts)

    def respond(_prompt: str, _schema: type[BaseModel]) -> BaseModel:
        return SummaryDraft(text=queue.pop(0) if len(queue) > 1 else queue[0])

    return FakeLLM(respond)


def test_grounded_summary_passes(profile: CandidateProfile, resume: TailoredResume) -> None:
    assert grounding_problems(GOOD, JOB, profile, resume) == []


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        (GOOD.replace("45%", "60%"), "numbers not supported by your profile: 60"),
        (GOOD + " Expert in Golang.", "terms not supported by your profile: Golang"),
        (GOOD + " 8+ years of experience.", "numbers not supported by your profile: 8"),
        (GOOD.replace(", and", " — and"), "no em dashes"),
        (GOOD * 3, "characters; keep it under 450"),
    ],
)
def test_ungrounded_or_off_style_summaries_are_rejected(
    profile: CandidateProfile, resume: TailoredResume, text: str, problem: str
) -> None:
    assert any(problem in p for p in grounding_problems(text, JOB, profile, resume))


def test_tailor_summary_retries_with_feedback(
    profile: CandidateProfile, resume: TailoredResume
) -> None:
    llm = _llm(GOOD + " Expert in Golang.", GOOD)

    assert tailor_summary(JOB, profile, resume, llm) == (GOOD, True)
    assert "Golang" in llm.prompts[1] and "rejected" in llm.prompts[1]
    first = llm.prompts[0]
    assert "<job_description>" in first and JOB.title in first and "untrusted" in first


def test_tailor_summary_falls_back_to_the_profile_summary(
    profile: CandidateProfile, resume: TailoredResume
) -> None:
    llm = _llm(GOOD + " Expert in Golang.")
    assert tailor_summary(JOB, profile, resume, llm) == (resume.summary, False)
