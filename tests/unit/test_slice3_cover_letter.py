import io
from pathlib import Path
from typing import Any

import pypdf
import pytest
import yaml
from pydantic import BaseModel

from src.agents.tailor.cover_letter import (
    CoverLetterDraft,
    CoverLetterError,
    to_text,
    write_cover_letter,
)
from src.agents.tailor.drafter import DraftPlan, review
from src.ingestion.base import RawJobPosting
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile
from tests.fakes import FakeLLM

ROOT = Path(__file__).resolve().parents[2]
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
JD = "Hooli needs a backend engineer to scale payments to 10x traffic. Python required."
JOB = RawJobPosting("Senior Backend Engineer", "Hooli", "San Francisco, CA", "u", JD, "greenhouse")
GOOD = CoverLetterDraft(
    greeting="Dear Hooli Hiring Team,",
    paragraphs=[
        "I am excited to apply for the Senior Backend Engineer role at Hooli.",
        "At Alpha Technologies I architected an ingestion pipeline handling 25,000 requests per "
        "second with 99.99% uptime, and I would bring that focus to scaling to 10x traffic.",
        "I would welcome the chance to discuss how I can help.",
    ],
    closing="Sincerely,",
)


@pytest.fixture
def profile() -> CandidateProfile:
    raw: dict[str, Any] = interpolate(
        yaml.safe_load((ROOT / "profile" / "candidate_profile.template.yaml").read_text()), ENV
    )
    return CandidateProfile.model_validate(raw)


def _resume(profile: CandidateProfile) -> Any:
    return review(
        DraftPlan(keywords=["Python"], bullet_ids=["b_alpha_1", "b_beta_1"]), JOB, profile
    )


def _llm(*drafts: CoverLetterDraft) -> FakeLLM:
    queue = list(drafts)

    def respond(_prompt: str, _schema: type[BaseModel]) -> BaseModel:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return FakeLLM(respond)


def test_cover_letter_pdf_and_txt_export(profile: CandidateProfile) -> None:
    letter = write_cover_letter(JOB, profile, _resume(profile), _llm(GOOD))

    assert letter.pdf.startswith(b"%PDF-")
    pages = pypdf.PdfReader(io.BytesIO(letter.pdf)).pages
    assert len(pages) == 1
    assert "25,000 requests" in pages[0].extract_text() and "Jane Doe" in pages[0].extract_text()

    assert letter.text == to_text(GOOD, profile)
    assert letter.text.startswith("Dear Hooli Hiring Team,\n\nI am excited")
    assert "\n\n".join(GOOD.paragraphs) in letter.text
    assert letter.text.endswith("Sincerely,\nJane Doe\n")
    assert "*" not in letter.text and "#" not in letter.text


def test_invented_numbers_are_rejected_then_retried(profile: CandidateProfile) -> None:
    invented = GOOD.model_copy(
        update={"paragraphs": ["I cut latency by 73% and led a team of 17.", *GOOD.paragraphs[1:]]}
    )
    llm = _llm(invented, GOOD)

    letter = write_cover_letter(JOB, profile, _resume(profile), llm)

    assert letter.text == to_text(GOOD, profile)
    assert len(llm.prompts) == 2
    assert "73" in llm.prompts[1] and "17" in llm.prompts[1]


@pytest.mark.parametrize(
    ("paragraph", "problem"),
    [
        ("Dear [Hiring Manager], I love [Company].", "placeholder"),
        ("word " * 401, "400 words"),
        ("I improved uptime to 99.5%.", "99.5"),
    ],
)
def test_unfixable_drafts_raise(profile: CandidateProfile, paragraph: str, problem: str) -> None:
    bad = GOOD.model_copy(update={"paragraphs": [paragraph]})
    llm = _llm(bad)
    with pytest.raises(CoverLetterError, match=problem):
        write_cover_letter(JOB, profile, _resume(profile), llm)
    assert len(llm.prompts) == 2


def test_prompt_lists_verified_facts_and_fences_jd(profile: CandidateProfile) -> None:
    llm = _llm(GOOD)
    write_cover_letter(JOB, profile, _resume(profile), llm)
    prompt = llm.prompts[0]
    assert "25,000 requests per second" in prompt  # kept bullet
    assert "Reduced P99 database query latency" not in prompt  # bullet not on this resume
    assert profile.star_stories[0].result in prompt
    assert f"<job_description>\n{JD}\n</job_description>" in prompt
    assert "untrusted" in prompt
