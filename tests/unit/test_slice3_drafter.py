from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import BaseModel

from src.agents.tailor.drafter import DraftPlan, ReviewError, draft_resume, page_budget, review
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
JD = "We need Python, FastAPI, Kafka and PostgreSQL experience. Redis caching is a plus."
JOB = RawJobPosting("Senior Backend Engineer", "Hooli", "San Francisco, CA", "u", JD, "greenhouse")


@pytest.fixture
def profile() -> CandidateProfile:
    raw: dict[str, Any] = interpolate(
        yaml.safe_load((ROOT / "profile" / "candidate_profile.template.yaml").read_text()), ENV
    )
    return CandidateProfile.model_validate(raw)


def _llm(*plans: DraftPlan) -> FakeLLM:
    queue = list(plans)

    def respond(_prompt: str, _schema: type[BaseModel]) -> BaseModel:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return FakeLLM(respond)


@pytest.mark.parametrize(
    ("location", "pages"),
    [
        ("San Francisco, CA", 1),  # tier 1 hub
        ("Denver, United States", 1),  # citizen country
        ("Berlin, Germany", 2),
        ("Lagos, Nigeria", 2),  # unclassified = international
    ],
)
def test_page_budget_selection_domestic_vs_international(
    profile: CandidateProfile, location: str, pages: int
) -> None:
    assert page_budget(location, profile) == pages


def test_draft_orders_roles_by_profile_and_bullets_by_rank(profile: CandidateProfile) -> None:
    plan = DraftPlan(
        keywords=["Python", "Kafka", "Redis"], bullet_ids=["b_alpha_2", "b_beta_1", "b_alpha_1"]
    )
    resume = draft_resume(JOB, profile, _llm(plan))

    assert [role.id for role, _ in resume.roles] == ["exp_company_alpha", "exp_company_beta"]
    assert [b.id for b in resume.roles[0][1]] == ["b_alpha_2", "b_alpha_1"]
    assert resume.keywords == ("Python", "Kafka", "Redis")
    assert resume.ranked_ids == ("b_alpha_2", "b_beta_1", "b_alpha_1")


def test_mandatory_roles_included(profile: CandidateProfile) -> None:
    resume = draft_resume(
        JOB, profile, _llm(DraftPlan(keywords=["Python"], bullet_ids=["b_alpha_1"]))
    )
    assert [role.id for role, _ in resume.roles] == [r.id for r in profile.work_experience]
    assert [b.id for b in resume.roles[1][1]] == ["b_beta_1"]  # auto-included, ranked last
    assert resume.ranked_ids[-1] == "b_beta_1"


def test_drafter_reviewer_zero_hallucination_gate(profile: CandidateProfile) -> None:
    fake = DraftPlan(keywords=["Python"], bullet_ids=["b_alpha_1", "b_invented_99"])
    with pytest.raises(ReviewError, match="b_invented_99"):
        review(fake, JOB, profile)


def test_drafter_retries_with_reviewer_feedback(profile: CandidateProfile) -> None:
    bad = DraftPlan(keywords=["Python"], bullet_ids=["b_invented_99"])
    good = DraftPlan(keywords=["Python"], bullet_ids=["b_alpha_1", "b_beta_1"])
    llm = _llm(bad, good)

    resume = draft_resume(JOB, profile, llm)

    assert resume.ranked_ids == ("b_alpha_1", "b_beta_1")
    assert len(llm.prompts) == 2
    assert "b_invented_99" in llm.prompts[1] and "not in the profile" in llm.prompts[1]


def test_drafter_gives_up_after_repeated_hallucinations(profile: CandidateProfile) -> None:
    llm = _llm(DraftPlan(keywords=[], bullet_ids=["b_invented_99"]))
    with pytest.raises(ReviewError):
        draft_resume(JOB, profile, llm)
    assert len(llm.prompts) == 2


def test_review_drops_duplicates_and_keywords_absent_from_jd(profile: CandidateProfile) -> None:
    plan = DraftPlan(
        keywords=["python", "Kubernetes", "PostgreSQL", "Python"],
        bullet_ids=["b_alpha_1", "b_alpha_1", "b_beta_1"],
    )
    resume = review(plan, JOB, profile)
    assert resume.keywords == (
        "python",
        "PostgreSQL",
    )  # case-insensitive dedupe; Kubernetes not in JD
    assert resume.ranked_ids == ("b_alpha_1", "b_beta_1")


def test_prompt_lists_bullets_and_fences_the_job_description(profile: CandidateProfile) -> None:
    llm = _llm(DraftPlan(keywords=[], bullet_ids=["b_alpha_1", "b_beta_1"]))
    draft_resume(JOB, profile, llm)
    prompt = llm.prompts[0]
    for bullet in profile.bullets:
        assert f"[{bullet.id}] {bullet.text}" in prompt
    assert f"<job_description>\n{JD}\n</job_description>" in prompt
    assert "untrusted" in prompt
