"""Typed schema for `candidate_profile.yaml`.

Models are frozen and use tuples, so a validated profile can be shared safely
(e.g. as the scheduler's per-cycle snapshot). Unknown keys are rejected to
catch typos in hand-edited YAML.
"""

import hashlib
import re
from collections import Counter
from collections.abc import Iterable
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
YearMonth = Annotated[str, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
HttpUrlStr = Annotated[str, StringConstraints(pattern=r"^https?://\S+$")]
Recency = Literal["24h", "48h", "72h", "1w", "2w", "4w", "1m", "any"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _reject_duplicates(kind: str, ids: Iterable[str]) -> None:
    dupes = sorted(i for i, n in Counter(ids).items() if n > 1)
    if dupes:
        raise ValueError(f"Duplicate {kind} id(s): {', '.join(dupes)}")


class Location(_Model):
    city: NonEmptyStr
    state: str | None = None
    country: NonEmptyStr
    postal_code: str | None = None
    timezone: str | None = None


class Links(_Model):
    linkedin: HttpUrlStr  # Rendered verbatim on every generated document.
    github: HttpUrlStr | None = None
    portfolio: HttpUrlStr | None = None


class WorkAuthorization(_Model):
    citizen_countries: tuple[NonEmptyStr, ...] = Field(min_length=1)
    requires_visa_for_international: bool
    sponsorship_needed: NonEmptyStr


class PersonalInfo(_Model):
    full_name: NonEmptyStr
    email: EmailStr
    phone: NonEmptyStr
    location: Location
    links: Links
    work_authorization: WorkAuthorization


class MarketTier(_Model):
    description: str = ""
    boost: int
    # Boost for standard_hubs and country-level matches; falls back to `boost` when unset.
    standard_boost: int | None = None
    domestic: bool = False  # Home-market tier (the first tier is always domestic).
    hubs: tuple[str, ...] = ()
    standard_hubs: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()


class PageBudget(_Model):
    domestic: int = Field(ge=1)
    international: int = Field(ge=1)
    cover_letter: int = Field(ge=1)


class WatchedCompany(_Model):
    """A company job board polled directly via its ATS's public API."""

    name: NonEmptyStr
    ats: Literal["greenhouse", "lever", "ashby", "workable"]
    board: Annotated[
        str, StringConstraints(pattern=r"^[A-Za-z0-9_-]+$")
    ]  # e.g. boards.greenhouse.io/<board>


class LinkedInSearch(_Model):
    """LinkedIn employer discovery: only offsite-apply jobs, resolved to the employer's ATS."""

    enabled: bool = False
    locations: tuple[NonEmptyStr, ...] = ()  # One search per target role and location.
    results_per_search: int = Field(default=10, ge=1, le=25)


class Preferences(_Model):
    target_roles: tuple[NonEmptyStr, ...] = Field(min_length=1)
    # Ordered highest priority first; keys are free-form tier names.
    sourcing_hierarchy: dict[str, MarketTier] = Field(min_length=1)
    excluded_employers: tuple[NonEmptyStr, ...] = ()
    cv_page_budget_rules: PageBudget
    watched_companies: tuple[WatchedCompany, ...] = ()
    linkedin: LinkedInSearch = LinkedInSearch()
    # Overrides the total computed from work_experience dates (e.g. to exclude internships).
    years_of_experience: float | None = Field(default=None, ge=0)
    job_recency: Recency = "1w"  # Only discover and save postings published this recently.
    # Stored jobs older than this (by posting date, else discovery date) are deactivated.
    job_max_age: Recency = "any"
    min_base_salary: int | None = Field(default=None, ge=0)  # Annual floor, in `currency`.
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] | None = None  # ISO 4217

    @model_validator(mode="after")
    def _check_salary_currency(self) -> Self:
        if self.min_base_salary is not None and self.currency is None:
            raise ValueError("min_base_salary requires a currency (e.g. INR, EUR, USD)")
        return self


class Skill(_Model):
    name: NonEmptyStr
    proficiency: Literal["beginner", "intermediate", "advanced", "expert"]
    years_of_experience: float = Field(ge=0)
    last_used_year: int | None = None


class AtomicBullet(_Model):
    id: NonEmptyStr
    text: NonEmptyStr
    skills: tuple[NonEmptyStr, ...] = ()
    metrics: dict[str, int | float | str] = Field(default_factory=dict)
    tags: tuple[NonEmptyStr, ...] = ()

    @property
    def fact_hash(self) -> str:
        """Deterministic fingerprint of the verified claim, used to detect edits."""
        return hashlib.sha256(" ".join(self.text.split()).encode()).hexdigest()


class WorkExperience(_Model):
    id: NonEmptyStr
    company: NonEmptyStr
    title: NonEmptyStr
    location: str | None = None
    start_date: YearMonth
    end_date: YearMonth | None = None
    is_current: bool = False
    summary: str | None = None
    atomic_bullets: tuple[AtomicBullet, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_dates(self) -> Self:
        if self.is_current and self.end_date is not None:
            raise ValueError(f"{self.id}: current role must not have an end_date")
        if not self.is_current and self.end_date is None:
            raise ValueError(f"{self.id}: past role needs an end_date (or is_current: true)")
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError(f"{self.id}: end_date is before start_date")
        return self


class Education(_Model):
    institution: NonEmptyStr
    degree: NonEmptyStr
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    gpa: str | None = None
    topics: tuple[str, ...] = ()


class Certification(_Model):
    name: NonEmptyStr
    issuer: NonEmptyStr
    year: int | None = None


class STARStory(_Model):
    id: NonEmptyStr
    situation: NonEmptyStr
    task: NonEmptyStr
    action: NonEmptyStr
    result: NonEmptyStr


class ScreeningQuestion(_Model):
    question_pattern: NonEmptyStr
    answer_type: Literal["boolean", "number", "text"]
    answer_value: bool | int | float | str

    @model_validator(mode="after")
    def _check(self) -> Self:
        try:
            re.compile(self.question_pattern)
        except re.error as exc:
            raise ValueError(f"Invalid regex {self.question_pattern!r}: {exc}") from exc
        value, kind = self.answer_value, self.answer_type
        ok = (
            isinstance(value, bool)
            if kind == "boolean"
            else isinstance(value, str)
            if kind == "text"
            else isinstance(value, int | float) and not isinstance(value, bool)
        )
        if not ok:
            raise ValueError(f"answer_value {value!r} does not match answer_type {kind!r}")
        return self


class CandidateProfile(_Model):
    personal_info: PersonalInfo
    preferences: Preferences
    skills_inventory: dict[str, tuple[Skill, ...]] = Field(default_factory=dict)
    work_experience: tuple[WorkExperience, ...] = Field(min_length=1)
    education: tuple[Education, ...] = ()
    certifications: tuple[Certification, ...] = ()
    star_stories: tuple[STARStory, ...] = ()
    screening_question_bank: tuple[ScreeningQuestion, ...] = ()

    @property
    def bullets(self) -> tuple[AtomicBullet, ...]:
        return tuple(b for role in self.work_experience for b in role.atomic_bullets)

    @model_validator(mode="after")
    def _check_unique_ids(self) -> Self:
        _reject_duplicates("work_experience", (r.id for r in self.work_experience))
        _reject_duplicates("atomic bullet", (b.id for b in self.bullets))
        _reject_duplicates("STAR story", (s.id for s in self.star_stories))
        return self
