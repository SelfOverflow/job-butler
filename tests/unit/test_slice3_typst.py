import io
from dataclasses import replace
from pathlib import Path
from typing import Any

import pypdf
import pytest
import yaml

from src.agents.tailor.drafter import DraftPlan, review
from src.agents.tailor.typst_engine import (
    FitError,
    fit_to_budget,
    page_count,
    render_pdf,
    resume_data,
)
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
    assert text.index("Technical Skills") < text.index("Professional Experience")


def test_course_completions_are_labelled_as_courses() -> None:
    raw = _raw()
    raw["certifications"] = [
        {
            "name": "AWS Certified Solutions Architect",
            "issuer": "Amazon Web Services",
            "year": 2024,
        },
        {
            "name": "AWS Cloud Practitioner Essentials",
            "issuer": "Amazon Web Services",
            "kind": "course",
            "platform": "Coursera",
            "year": 2026,
        },
    ]
    profile = CandidateProfile.model_validate(raw)
    resume = review(DraftPlan(keywords=["Python"], bullet_ids=["b_alpha_1"]), JOB, profile)

    data = resume_data(resume, profile, resume.ranked_ids)
    assert data["certifications_heading"] == "Certifications & Courses"
    assert data["certifications"] == [
        "AWS Certified Solutions Architect, Amazon Web Services (2024)",
        "AWS Cloud Practitioner Essentials (course completion), Amazon Web Services"
        " via Coursera (2026)",
    ]
    text = _text(render_pdf(resume, profile, resume.ranked_ids))
    assert "Certifications & Courses" in text and "(course completion)" in text


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


def test_skills_section_leads_with_matched_skills() -> None:
    profile = CandidateProfile.model_validate(_raw())
    plan = DraftPlan(
        keywords=["Kafka", "Postgresql", "AWS Lambda", "Rust"], bullet_ids=["b_alpha_1"]
    )
    resume = review(plan, replace(JOB, description="Kafka postgresql AWS Lambda Rust"), profile)

    skills = resume_data(resume, profile, set(resume.ranked_ids))["skills"]

    # Kafka only exists as a tag on the kept bullet b_alpha_1; Rust is not a verified skill.
    assert skills[0] == {"label": "Relevant to this role", "names": ["Kafka", "PostgreSQL", "AWS"]}
    groups = [g["label"] for g in skills[1:]]
    assert groups == ["Cloud and infrastructure", "Languages and frameworks"]  # 2 matches vs 0
    assert skills[1]["names"][:2] == ["AWS", "PostgreSQL"]  # matched skills first, stable order


def test_skills_section_without_matches_keeps_profile_order() -> None:
    profile = CandidateProfile.model_validate(_raw())
    resume = review(DraftPlan(keywords=[], bullet_ids=["b_alpha_1"]), JOB, profile)
    skills = resume_data(resume, profile, set(resume.ranked_ids))["skills"]
    assert [g["label"] for g in skills] == ["Languages and frameworks", "Cloud and infrastructure"]


def test_js_shorthand_matches_only_the_exact_keyword() -> None:
    raw = _raw()
    raw["skills_inventory"] = {
        "web": [{"name": "React.js", "proficiency": "expert", "years_of_experience": 5}]
    }
    profile = CandidateProfile.model_validate(raw)
    for keywords, expected in ((["React Native"], []), (["React"], ["React.js"])):
        plan = DraftPlan(keywords=keywords, bullet_ids=["b_beta_1"])
        job = replace(JOB, description="React Native and React")
        resume = review(plan, job, profile)
        skills = resume_data(resume, profile, set(resume.ranked_ids))["skills"]
        relevant = skills[0]["names"] if skills[0]["label"] == "Relevant to this role" else []
        assert [n for n in relevant if n == "React.js"] == expected


def test_one_relevant_skill_per_keyword() -> None:
    raw = _raw()
    raw["skills_inventory"] = {
        "ci": [{"name": "GitHub Actions CI/CD", "proficiency": "expert", "years_of_experience": 4}]
    }
    raw["work_experience"][1]["atomic_bullets"][0]["skills"] = ["GitHub Actions"]
    profile = CandidateProfile.model_validate(raw)
    plan = DraftPlan(keywords=["GitHub Actions"], bullet_ids=["b_beta_1"])
    resume = review(plan, replace(JOB, description="GitHub Actions"), profile)
    skills = resume_data(resume, profile, set(resume.ranked_ids))["skills"]
    assert skills[0]["names"] == ["GitHub Actions CI/CD"]
