from pathlib import Path

import yaml

from src.profile.exporter import format_month, to_markdown
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile

TEMPLATE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "Springfield",
    "CANDIDATE_STATE": "State",
    "CANDIDATE_POSTAL_CODE": "00000",
}


def _profile() -> CandidateProfile:
    raw = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    return CandidateProfile.model_validate(interpolate(raw, ENV))


def test_format_month() -> None:
    assert format_month("2023-01") == "Jan 2023"
    assert format_month("2022-12") == "Dec 2022"
    assert format_month(None) == "Present"


def test_master_resume_has_ats_headings_in_order() -> None:
    md = to_markdown(_profile())
    headings = [line for line in md.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Professional Experience",
        "## Technical Skills",
        "## Education",
        "## Certifications",
    ]
    assert md.startswith("# Jane Doe\n")


def test_master_resume_contact_line_is_verbatim() -> None:
    md = to_markdown(_profile())
    contact = md.splitlines()[2]
    assert contact == (
        "jane.doe@example.com | +1 555 0100 | Springfield, State, United States | "
        "https://www.linkedin.com/in/janedoe | https://github.com/janedoe | https://janedoe.dev"
    )


def test_master_resume_includes_every_role_and_bullet() -> None:
    profile = _profile()
    md = to_markdown(profile)
    assert "### Senior Backend Engineer, Alpha Technologies" in md
    assert "Jan 2023 - Present | New York, NY (Remote)" in md
    assert "Jun 2020 - Dec 2022 | Boston, MA" in md
    for bullet in profile.bullets:
        assert f"- {bullet.text}" in md


def test_master_resume_skills_education_certifications() -> None:
    md = to_markdown(_profile())
    assert "**Languages and frameworks:** Python, TypeScript, FastAPI, React" in md
    assert "**B.S., Computer Science**, University of Example (2016 - 2020) | GPA: 3.8 / 4.0" in md
    assert "- AWS Certified Solutions Architect, Amazon Web Services (2024)" in md
