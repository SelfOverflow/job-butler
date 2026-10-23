import pytest
from pydantic import BaseModel, ValidationError

from src.agents.llm import LLMError
from src.agents.tailor.ats_review import AtsReview, RequirementCheck, review_resume
from src.ingestion.base import RawJobPosting
from tests.fakes import FakeLLM

JD = "Senior Backend Engineer. Required: Python, Kafka. Nice to have: Golang."
JOB = RawJobPosting("Senior Backend Engineer", "Hooli", "Remote", "u", JD, "greenhouse")
REVIEW = AtsReview(
    score=78,
    verdict="shortlist",
    requirements=[
        RequirementCheck(requirement="Python", priority="required", status="covered"),
        RequirementCheck(
            requirement="Kafka", priority="required", status="missing_have_it", note="in skills"
        ),
        RequirementCheck(requirement="Golang", priority="preferred", status="gap"),
    ],
    issues=["Summary does not state years of experience"],
    ungrounded_claims=[],
)


def test_review_prompt_shows_the_ats_text_layer_facts_and_fenced_jd() -> None:
    llm = FakeLLM(lambda _p, _s: REVIEW)

    review = review_resume(JOB, "RESUME TEXT LAYER", ["Python (6 years)"], llm)

    assert review is REVIEW
    assert review.missing_have_it == ["Kafka"] and review.gaps == ["Golang"]
    prompt = llm.prompts[0]
    assert "RESUME TEXT LAYER" in prompt and "Python (6 years)" in prompt
    assert "<job_description>" in prompt and "untrusted" in prompt
    for rule in ("exact job title", "literal", "headings", "dates", "30-second"):
        assert rule in prompt


def test_review_failure_is_reported_not_raised() -> None:
    def broken(_prompt: str, _schema: type[BaseModel]) -> BaseModel:
        raise LLMError("quota exceeded")

    assert review_resume(JOB, "text", [], FakeLLM(broken)) is None


def test_score_is_bounded() -> None:
    with pytest.raises(ValidationError):
        AtsReview(score=140, verdict="shortlist", requirements=[], issues=[], ungrounded_claims=[])
