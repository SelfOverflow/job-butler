"""Years-of-experience gate: never surface roles that require more than the candidate has.

`required_years` reads every "N+ years" requirement in a job description and
returns the highest minimum. A phrase counts when its sentence mentions
experience, when it is followed by work wording ("9+ years in Python"), or when
it follows a requirement cue ("Required Qualifications: 6 years"). The gate errs
toward excluding a role rather than recommending one the candidate does not
qualify for.
"""

import re
from datetime import date

from src.profile.models import CandidateProfile

_WORD_NUMBERS = {
    w: i
    for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen "
        "fourteen fifteen".split()
    )
}
_NUM = r"\d{1,2}|" + "|".join(_WORD_NUMBERS)
_YEARS = re.compile(
    rf"\b(?P<min>{_NUM})\s*\+?(?:\s*(?:-|–|—|to)\s*(?:{_NUM})\s*\+?)?(?:\s*or\s+more)?"
    r"\s*(?:years?|yrs?)\b",
    re.IGNORECASE,
)
_EXPERIENCE = re.compile(r"experien|\bexp\b", re.IGNORECASE)
# "9+ years in Python", "6-8+ years building ...": the phrase itself reads as a requirement.
_WORK_AFTER = re.compile(
    r"^\W*(?:of|in|with|as|building|developing|working|designing|leading|writing|using|"
    r"hands-on|professional|industry|relevant|software|engineering|programming|coding)\b",
    re.IGNORECASE,
)
# "Required Qualifications: 6 years", "minimum 7 years", "you bring 4 years".
_REQUIREMENT_BEFORE = re.compile(
    r"(?:requir\w*|qualifications?|minimum(?:\s+of)?|at\s+least|must\s+have|you\s+bring)\W*$",
    re.IGNORECASE,
)
_SENTENCE_BREAK = re.compile(r"[.;\n!?]")
_NOT_EXPERIENCE = re.compile(r"^\W*(?:of\s+age|old|ago)\b", re.IGNORECASE)


def required_years(description: str) -> int | None:
    """Highest minimum years of experience the description asks for, or None."""
    found: list[int] = []
    for match in _YEARS.finditer(description):
        before = _SENTENCE_BREAK.split(description[max(0, match.start() - 50) : match.start()])[-1]
        after = _SENTENCE_BREAK.split(description[match.end() : match.end() + 70])[0]
        if _NOT_EXPERIENCE.match(after):
            continue
        if not (
            _EXPERIENCE.search(f"{before} {after}")
            or _WORK_AFTER.match(after)
            or _REQUIREMENT_BEFORE.search(before)
        ):
            continue
        raw = match.group("min").lower()
        found.append(_WORD_NUMBERS[raw] if raw in _WORD_NUMBERS else int(raw))
    return max(found, default=None)


def _month_index(year_month: str) -> int:
    year, month = year_month.split("-")
    return int(year) * 12 + int(month) - 1


def total_experience_years(profile: CandidateProfile, today: date | None = None) -> float:
    """Explicit `preferences.years_of_experience`, else merged work_experience spans."""
    if profile.preferences.years_of_experience is not None:
        return profile.preferences.years_of_experience
    today = today or date.today()
    now = today.year * 12 + today.month - 1
    spans = sorted(
        (_month_index(r.start_date), _month_index(r.end_date) if r.end_date else now)
        for r in profile.work_experience
    )
    months, cursor = 0, -1
    for start, end in spans:  # Merge overlaps so concurrent roles are not double-counted.
        start = max(start, cursor)
        if end > start:
            months += end - start
            cursor = end
    return months / 12
