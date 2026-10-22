from typing import Any

import pytest

from src.profile.models import ScreeningQuestion
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
