from pathlib import Path
from typing import Any

import pytest
import typst
import yaml

from src.agents.tailor.drafter import DraftPlan, review
from src.agents.tailor.pdf_verifier import verify_pdf
from src.agents.tailor.typst_engine import render_pdf
from src.ingestion.base import RawJobPosting
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile

ROOT = Path(__file__).resolve().parents[2]
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}
JOB = RawJobPosting("Engineer", "Hooli", "San Francisco, CA", "u", "Python Kafka", "x")


def _profile(**links: str) -> CandidateProfile:
    raw: dict[str, Any] = interpolate(
        yaml.safe_load((ROOT / "profile" / "candidate_profile.template.yaml").read_text()), ENV
    )
    raw["personal_info"]["links"].update(links)
    return CandidateProfile.model_validate(raw)


def _pdf(profile: CandidateProfile, bullet_text: str | None = None) -> bytes:
    if bullet_text is not None:
        raw = profile.model_dump()
        raw["work_experience"][0]["atomic_bullets"][0]["text"] = bullet_text
        profile = CandidateProfile.model_validate(raw)
    resume = review(DraftPlan(keywords=[], bullet_ids=["b_alpha_1"]), JOB, profile)
    return render_pdf(resume, profile, resume.ranked_ids)


def test_pdf_text_layer_verifier() -> None:
    profile = _profile()
    report = verify_pdf(
        _pdf(profile), profile, keywords=["Python", "PostgreSQL", "Rust"], max_pages=1
    )

    assert report.passed, report.problems
    assert report.pages == 1
    assert report.checks == {"text": True, "linkedin": True, "contact": True, "pages": True}
    assert report.keywords_matched == ["Python", "PostgreSQL"]
    assert report.keywords_missing == ["Rust"]


def test_missing_verbatim_linkedin_fails() -> None:
    rendered = _profile(linkedin="https://www.linkedin.com/in/someone-else")
    report = verify_pdf(_pdf(rendered), _profile(), keywords=[], max_pages=1)
    assert not report.passed and not report.checks["linkedin"]
    assert any("LinkedIn" in p for p in report.problems)


def test_page_budget_exceeded_fails() -> None:
    profile = _profile()
    report = verify_pdf(_pdf(profile), profile, keywords=[], max_pages=0)
    assert not report.checks["pages"] and "1 page(s), budget 0" in " ".join(report.problems)


@pytest.mark.parametrize("glitch", ["� broken glyph", "(cid:72)(cid:105)"])
def test_replacement_glyphs_fail_text_check(glitch: str) -> None:
    profile = _profile()
    report = verify_pdf(_pdf(profile, bullet_text=f"Shipped {glitch}"), profile, [], max_pages=1)
    assert not report.checks["text"]


def test_image_only_or_empty_pdf_fails(tmp_path: Path) -> None:
    blank = tmp_path / "blank.typ"
    blank.write_text("#box(width: 10pt, height: 10pt, fill: black)")
    report = verify_pdf(typst.compile(str(blank)), _profile(), keywords=[], max_pages=1)
    assert not report.passed
    assert report.checks == {"text": False, "linkedin": False, "contact": False, "pages": True}


def test_unreadable_bytes_fail_cleanly() -> None:
    report = verify_pdf(b"not a pdf", _profile(), keywords=[], max_pages=1)
    assert not report.passed and report.pages == 0
