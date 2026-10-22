import io
from pathlib import Path
from typing import Any

import pypdf
import pytest
import yaml

from src.agents.tailor.drafter import DraftPlan, review
from src.agents.tailor.typst_engine import FitError, fit_to_budget, page_count, render_pdf
from src.ingestion.base import RawJobPosting
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile

ROOT = Path(__file__).resolve().parents[2]
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "Springfield",
    "CANDIDATE_STATE": "State",
    "CANDIDATE_POSTAL_CODE": "0",
}
JOB = RawJobPosting(
    "Senior Backend Engineer", "Hooli", "San Francisco, CA", "u", "Python Kafka", "x"
)
FILLER = (
    "Delivered a measurable improvement to a production system used by many customers daily. " * 2
)


def _raw() -> dict[str, Any]:
    raw: dict[str, Any] = interpolate(
        yaml.safe_load((ROOT / "profile" / "candidate_profile.template.yaml").read_text()), ENV
    )
    return raw


def _text(pdf: bytes) -> str:
    return "\n".join(page.extract_text() for page in pypdf.PdfReader(io.BytesIO(pdf)).pages)


def _big_profile(roles: int, bullets_per_role: int) -> CandidateProfile:
    raw = _raw()
    template_role = raw["work_experience"][1]
    raw["work_experience"] = [
        {
            **template_role,
            "id": f"exp_{r}",
            "company": f"Company {r}",
            "atomic_bullets": [
                {"id": f"b_{r}_{i}", "text": f"Role {r} bullet {i}. {FILLER}"}
                for i in range(bullets_per_role)
            ],
        }
        for r in range(roles)
    ]
    return CandidateProfile.model_validate(raw)


def test_typst_single_column_pdf_compilation() -> None:
    profile = CandidateProfile.model_validate(_raw())
    resume = review(DraftPlan(keywords=["Python"], bullet_ids=["b_alpha_1"]), JOB, profile)

    pdf = render_pdf(resume, profile, resume.ranked_ids)

    assert pdf.startswith(b"%PDF-")
    assert page_count(pdf) == 1
    text = _text(pdf)
    assert "https://www.linkedin.com/in/janedoe" in text
    assert "+1 555 0100" in text and "Springfield" in text
    for role in profile.work_experience:
        assert role.title in text and role.company in text
    assert "Jan 2023 - Present" in text and "Jun 2020 - Dec 2022" in text
    assert "Professional Experience" in text and "Technical Skills" in text and "Education" in text


def test_profile_text_is_rendered_literally() -> None:
    raw = _raw()
    raw["work_experience"][0]["atomic_bullets"][0]["text"] = (
        "Cut costs by 30% #wins $5k *fast* _now_ <b>"
    )
    profile = CandidateProfile.model_validate(raw)
    resume = review(DraftPlan(keywords=[], bullet_ids=["b_alpha_1"]), JOB, profile)
    assert "Cut costs by 30% #wins $5k *fast* _now_ <b>" in _text(
        render_pdf(resume, profile, resume.ranked_ids)
    )


def test_fit_to_budget_drops_lowest_ranked_bullets_but_keeps_every_role() -> None:
    profile = _big_profile(roles=3, bullets_per_role=8)
    ranked = [b.id for b in profile.bullets]
    resume = review(DraftPlan(keywords=[], bullet_ids=ranked), JOB, profile)
    assert page_count(render_pdf(resume, profile, resume.ranked_ids)) > 1

    pdf, kept = fit_to_budget(resume, profile)

    assert page_count(pdf) == resume.pages == 1
    assert 3 <= len(kept) < len(ranked)
    assert kept == tuple(i for i in ranked if i in kept)  # rank order preserved
    for role in profile.work_experience:
        assert any(b.id in kept for b in role.atomic_bullets)
    dropped = [i for i in ranked if i not in kept]
    first_role_kept = [i for i in kept if i.startswith("b_0_")]
    assert first_role_kept and dropped  # higher-ranked bullets survive over lower-ranked ones
    assert max(ranked.index(i) for i in first_role_kept) < max(ranked.index(i) for i in dropped)


def test_fit_to_budget_fails_when_one_bullet_per_role_cannot_fit() -> None:
    profile = _big_profile(roles=30, bullets_per_role=1)
    resume = review(DraftPlan(keywords=[], bullet_ids=[]), JOB, profile)
    with pytest.raises(FitError, match="1 page"):
        fit_to_budget(resume, profile)
