"""Answer ATS screening questions from the profile's `screening_question_bank`."""

import re
from collections.abc import Sequence

from src.profile.models import ScreeningQuestion


def resolve(question: str, bank: Sequence[ScreeningQuestion]) -> ScreeningQuestion | None:
    """Return the first bank entry whose pattern matches `question`, or None.

    Bank order is priority order: list specific patterns before general ones.
    """
    text = " ".join(question.split())  # Form labels often contain stray newlines/tabs.
    return next((q for q in bank if re.search(q.question_pattern, text)), None)
