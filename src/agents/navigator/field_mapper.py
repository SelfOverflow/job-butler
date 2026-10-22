"""Map application form fields to verified candidate data. Never guesses.

Precedence per field: the candidate's own answers (dashboard) > identity data
from the profile > tailored artifacts > the screening question bank. Choice
fields are filled only when one of the form's own options matches. Consent
checkboxes and demographic (EEO) questions are never auto-answered. Any
required field left without a safe value is returned in `unanswered` so the
application escalates to the candidate instead of being guessed.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from src.agents.tailor.runner import ArtifactPaths
from src.ingestion.base import contains_phrase, words
from src.profile.models import CandidateProfile
from src.profile.screening import resolve

Kind = Literal["text", "email", "tel", "url", "textarea", "select", "radio", "checkbox", "file"]
TEXT_KINDS = ("text", "email", "tel", "url", "textarea")
_SENSITIVE = re.compile(
    r"\b(gender|sex|pronouns?|race|racial|ethnic\w*|hispanic|latin[oax]|veteran|"
    r"disabilit\w*|disabled|sexual orientation|transgender)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    kind: Kind
    required: bool
    options: tuple[str, ...] = ()
    selector: str = ""  # Set by the form inspector; locates the control on the page.


@dataclass(frozen=True)
class PlannedField:
    field: FieldSpec
    value: str
    source: Literal["candidate", "profile", "resume", "cover_letter", "screening"]


@dataclass
class FillPlan:
    planned: list[PlannedField] = field(default_factory=list)
    unanswered: list[FieldSpec] = field(default_factory=list)


def _has(label: str, *phrases: str) -> bool:
    text = words(label)
    return any(contains_phrase(text, words(p)) for p in phrases)


def _identity(spec: FieldSpec, profile: CandidateProfile) -> str | None:
    info, links = profile.personal_info, profile.personal_info.links
    first, _, last = info.full_name.partition(" ")
    rules: list[tuple[Callable[[], bool], str | None]] = [
        (lambda: _has(spec.label, "first name", "given name"), first),
        (lambda: _has(spec.label, "last name", "surname", "family name"), last or None),
        (lambda: _has(spec.label, "full name") or words(spec.label) == ("name",), info.full_name),
        (lambda: _has(spec.label, "email"), info.email),
        (lambda: _has(spec.label, "phone", "mobile", "telephone"), info.phone),
        (lambda: _has(spec.label, "linkedin"), links.linkedin),
        (lambda: _has(spec.label, "github"), links.github),
        (lambda: _has(spec.label, "website", "portfolio", "personal site"), links.portfolio),
        (lambda: _has(spec.label, "country"), info.location.country),
        (
            lambda: _has(spec.label, "location", "city"),
            f"{info.location.city}, {info.location.country}",
        ),
    ]
    return next((value for matches, value in rules if matches()), None)


def _choose(spec: FieldSpec, value: str) -> str | None:
    """The form option matching `value` (exact, or same first word for yes/no), else None."""
    options = [o for o in spec.options if o.strip()]
    exact = [o for o in options if o.casefold() == value.casefold()]
    if exact:
        return exact[0]
    lead = [o for o in options if words(o)[:1] == words(value)[:1] and len(words(value)) == 1]
    return lead[0] if len(lead) == 1 else None


def _fit(spec: FieldSpec, value: str) -> str | None:
    if spec.kind in ("select", "radio"):
        return _choose(spec, value)
    if spec.kind == "checkbox":
        return "true" if value.strip().casefold() in ("yes", "true", "1", "checked") else "false"
    return value


def map_fields(
    fields: Sequence[FieldSpec],
    profile: CandidateProfile,
    artifacts: ArtifactPaths,
    answers: dict[str, str],
) -> FillPlan:
    plan = FillPlan()
    by_label = {label.casefold(): value for label, value in answers.items()}
    for spec in fields:
        planned = _plan_one(spec, profile, artifacts, by_label)
        if planned is not None:
            plan.planned.append(planned)
        elif spec.required:
            plan.unanswered.append(spec)
    return plan


def _plan_one(
    spec: FieldSpec, profile: CandidateProfile, artifacts: ArtifactPaths, answers: dict[str, str]
) -> PlannedField | None:
    if (given := answers.get(spec.label.casefold())) is not None:
        value = _fit(spec, given)
        return PlannedField(spec, value, "candidate") if value is not None else None
    if spec.kind == "checkbox" or _SENSITIVE.search(spec.label):
        return None  # Consent and demographic answers only ever come from the candidate.
    if spec.kind == "file":
        if _has(spec.label, "resume", "cv"):
            return PlannedField(spec, str(artifacts.resume), "resume")
        if _has(spec.label, "cover letter"):
            return PlannedField(spec, str(artifacts.cover_pdf), "cover_letter")
        return None
    if _has(spec.label, "cover letter") and spec.kind == "textarea":
        if artifacts.cover_txt.is_file():
            return PlannedField(
                spec, artifacts.cover_txt.read_text(encoding="utf-8"), "cover_letter"
            )
        return None
    if spec.kind in TEXT_KINDS and (identity := _identity(spec, profile)) is not None:
        return PlannedField(spec, identity, "profile")
    match = resolve(spec.label, profile.screening_question_bank)
    if match is None:
        return None
    raw = match.answer_value
    text = ("Yes" if raw else "No") if isinstance(raw, bool) else str(raw)
    value = _fit(spec, text)
    return PlannedField(spec, value, "screening") if value is not None else None
