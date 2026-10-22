from pathlib import Path
from typing import Any

import pytest
import yaml

from src.profile.loader import interpolate
from src.profile.models import CandidateProfile, ScreeningQuestion
from src.profile.screening import resolve


def _q(pattern: str, answer_type: str, value: Any) -> ScreeningQuestion:
    return ScreeningQuestion(question_pattern=pattern, answer_type=answer_type, answer_value=value)


BANK = (
    _q(r"(?i)authorized to work in india", "boolean", True),
    _q(r"(?i)require (visa )?sponsorship in india", "boolean", False),
    _q(r"(?i)require (visa )?sponsorship", "boolean", True),  # general fallback
    _q(r"(?i)notice period", "text", "30 days"),
    _q(r"(?i)years of experience with (python|react)", "number", 5),
)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Are you legally authorized to work in India?", True),
        ("Will you now or in the future require sponsorship in India?", False),
        ("Will you require visa sponsorship to work in Germany?", True),
        ("What is your notice period?", "30 days"),
        ("How many years of experience with Python do you have?", 5),
        ("ARE YOU AUTHORIZED TO WORK IN INDIA", True),
    ],
)
def test_screening_question_resolver(question: str, expected: Any) -> None:
    match = resolve(question, BANK)
    assert match is not None
    assert match.answer_value == expected


def test_first_matching_entry_wins() -> None:
    # Both sponsorship patterns match; the more specific one is listed first.
    match = resolve("Do you require sponsorship in India?", BANK)
    assert match is BANK[1]


def test_whitespace_in_form_labels_is_normalized() -> None:
    match = resolve("What is your\n  notice\tperiod?", BANK)
    assert match is not None
    assert match.answer_value == "30 days"


def test_unmatched_question_returns_none() -> None:
    assert resolve("What is your favourite colour?", BANK) is None
    assert resolve("What is your notice period?", ()) is None


ACTIVE_PROFILE = Path(__file__).resolve().parents[2] / "profile" / "candidate_profile.yaml"
FAKE_ENV = {
    "CANDIDATE_EMAIL": "x@example.com",
    "CANDIDATE_PHONE": "0",
    "CANDIDATE_CITY": "x",
    "CANDIDATE_STATE": "x",
    "CANDIDATE_POSTAL_CODE": "0",
}


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Are you authorized to work in India?", True),
        ("Will you require sponsorship in India?", False),
        ("Do you need visa sponsorship to work in India?", False),
        ("Will you require visa sponsorship to work in the UK?", True),
        ("Do you require sponsorship for employment in the United States?", True),
        ("Would you need sponsorship outside India?", True),
        ("Will you require sponsorship in India or the UK?", True),
        ("What is your notice period?", "30 days (negotiable)"),
        ("How many years of experience with React Native do you have?", 5),
        (
            "What are your salary expectations?",
            "Competitive market rate based on role and location",
        ),
        ("Current CTC?", "Competitive market rate based on role and location"),
    ],
)
def test_active_profile_screening_bank(question: str, expected: Any) -> None:
    raw = yaml.safe_load(ACTIVE_PROFILE.read_text(encoding="utf-8"))
    profile = CandidateProfile.model_validate(interpolate(raw, FAKE_ENV))
    match = resolve(question, profile.screening_question_bank)
    assert match is not None
    assert match.answer_value == expected
