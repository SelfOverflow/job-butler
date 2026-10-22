from pathlib import Path
from typing import Any

import pytest
import yaml

from src.agents.navigator.field_mapper import FieldSpec, Kind, map_fields
from src.agents.tailor.runner import artifact_paths
from src.profile.loader import interpolate
from src.profile.models import CandidateProfile

ROOT = Path(__file__).resolve().parents[2]
ENV = {"CANDIDATE_PHONE": "+1 555 0100", "CANDIDATE_CITY": "Springfield", "CANDIDATE_STATE": "IL",
       "CANDIDATE_POSTAL_CODE": "0"}  # fmt: skip
ARTIFACTS = artifact_paths(Path("/artifacts"), "job_1234abcd")


@pytest.fixture
def profile() -> CandidateProfile:
    raw: dict[str, Any] = interpolate(
        yaml.safe_load((ROOT / "profile" / "candidate_profile.template.yaml").read_text()), ENV
    )
    return CandidateProfile.model_validate(raw)


def _field(
    label: str, kind: Kind = "text", required: bool = True, options: tuple[str, ...] = ()
) -> FieldSpec:
    return FieldSpec(
        name=label.lower().replace(" ", "_"),
        label=label,
        kind=kind,
        required=required,
        options=options,
    )


def _plan(
    profile: CandidateProfile, *fields: FieldSpec, answers: dict[str, str] | None = None
) -> dict[str, tuple[str, str]]:
    plan = map_fields(list(fields), profile, ARTIFACTS, answers or {})
    return {p.field.label: (p.value, p.source) for p in plan.planned}


def test_field_mapper_standard_inputs(profile: CandidateProfile) -> None:
    planned = _plan(
        profile,
        _field("First Name"),
        _field("Last Name"),
        _field("Email", "email"),
        _field("Phone", "tel"),
        _field("LinkedIn Profile", "url"),
        _field("GitHub URL", "url", required=False),
        _field("Website", "url", required=False),
        _field("Current Location"),
        _field("Resume/CV", "file"),
        _field("Cover Letter", "file", required=False),
    )
    assert planned == {
        "First Name": ("Jane", "profile"),
        "Last Name": ("Doe", "profile"),
        "Email": ("jane.doe@example.com", "profile"),
        "Phone": ("+1 555 0100", "profile"),
        "LinkedIn Profile": ("https://www.linkedin.com/in/janedoe", "profile"),
        "GitHub URL": ("https://github.com/janedoe", "profile"),
        "Website": ("https://janedoe.dev", "profile"),
        "Current Location": ("Springfield, United States", "profile"),
        "Resume/CV": (str(ARTIFACTS.resume), "resume"),
        "Cover Letter": (str(ARTIFACTS.cover_pdf), "cover_letter"),
    }


def test_cover_letter_textarea_gets_plain_text(profile: CandidateProfile, tmp_path: Path) -> None:
    artifacts = artifact_paths(tmp_path, "job_1234abcd")
    artifacts.cover_txt.parent.mkdir(parents=True)
    artifacts.cover_txt.write_text("Dear team,\n\nHello.\n")
    plan = map_fields([_field("Cover Letter", "textarea")], profile, artifacts, {})
    assert [(p.value, p.source) for p in plan.planned] == [
        ("Dear team,\n\nHello.\n", "cover_letter")
    ]


def test_full_name_field(profile: CandidateProfile) -> None:
    assert _plan(profile, _field("Full Name"))["Full Name"] == ("Jane Doe", "profile")
    assert _plan(profile, _field("Name"))["Name"] == ("Jane Doe", "profile")


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        (
            _field("Are you authorized to work in the US?", "select", options=("", "Yes", "No")),
            "Yes",
        ),
        (_field("Do you require sponsorship?", "radio", options=("Yes", "No")), "No"),
        (_field("Do you require sponsorship?", "text"), "No"),
        (_field("Years of experience with Python", "text"), "6"),
        (_field("What is your notice period?", "textarea"), "2 weeks"),
    ],
)
def test_screening_answers_fill_typed_fields(
    profile: CandidateProfile, field: FieldSpec, expected: str
) -> None:
    assert _plan(profile, field)[field.label] == (expected, "screening")


def test_select_without_a_matching_option_is_escalated(profile: CandidateProfile) -> None:
    field = _field(
        "Are you authorized to work in the US?", "select", options=("Citizen", "Green card")
    )
    plan = map_fields([field], profile, ARTIFACTS, {})
    assert plan.planned == [] and [f.label for f in plan.unanswered] == [field.label]


@pytest.mark.parametrize(
    "field",
    [
        _field("Why do you want to work at Hooli?", "textarea"),
        _field("I agree to the privacy policy", "checkbox"),
        _field("Gender", "select", options=("Male", "Female", "Decline to self-identify")),
        _field(
            "Are you a protected veteran?", "radio", options=("Yes", "No", "I don't wish to answer")
        ),
        _field("Disability status", "select", options=("Yes", "No")),
    ],
)
def test_unanswerable_required_fields_are_escalated_never_guessed(
    profile: CandidateProfile, field: FieldSpec
) -> None:
    plan = map_fields([field], profile, ARTIFACTS, {})
    assert plan.planned == []
    assert [f.label for f in plan.unanswered] == [field.label]


def test_optional_sensitive_fields_are_left_blank(profile: CandidateProfile) -> None:
    plan = map_fields(
        [_field("Race / Ethnicity", "select", required=False, options=("A", "B"))],
        profile,
        ARTIFACTS,
        {},
    )
    assert plan.planned == [] and plan.unanswered == []


def test_candidate_answers_take_precedence(profile: CandidateProfile) -> None:
    answers = {
        "Why do you want to work at Hooli?": "Your mission.",
        "I agree to the privacy policy": "yes",
        "Gender": "Decline to self-identify",
        "Email": "other@example.com",
    }
    planned = _plan(
        profile,
        _field("Why do you want to work at Hooli?", "textarea"),
        _field("I agree to the privacy policy", "checkbox"),
        _field("Gender", "select", options=("Male", "Female", "Decline to self-identify")),
        _field("Email", "email"),
        answers=answers,
    )
    assert planned == {
        "Why do you want to work at Hooli?": ("Your mission.", "candidate"),
        "I agree to the privacy policy": ("true", "candidate"),
        "Gender": ("Decline to self-identify", "candidate"),
        "Email": ("other@example.com", "candidate"),
    }


def test_missing_optional_profile_value_is_skipped_but_required_is_escalated(
    profile: CandidateProfile,
) -> None:
    raw = profile.model_dump()
    raw["personal_info"]["links"]["portfolio"] = None
    no_site = CandidateProfile.model_validate(raw)
    optional = map_fields([_field("Website", "url", required=False)], no_site, ARTIFACTS, {})
    required = map_fields([_field("Website", "url")], no_site, ARTIFACTS, {})
    assert (optional.planned, optional.unanswered) == ([], [])
    assert [f.label for f in required.unanswered] == ["Website"]
