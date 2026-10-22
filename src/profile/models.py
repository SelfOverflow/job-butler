"""Typed schema for `candidate_profile.yaml`.

Models are frozen and use tuples, so a validated profile can be shared safely
(e.g. as the scheduler's per-cycle snapshot). Unknown keys are rejected to
catch typos in hand-edited YAML.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
HttpUrlStr = Annotated[str, StringConstraints(pattern=r"^https?://\S+$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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
    standard_boost: int = 0
    hubs: tuple[str, ...] = ()
    standard_hubs: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()


class PageBudget(_Model):
    domestic: int = Field(ge=1)
    international: int = Field(ge=1)
    cover_letter: int = Field(ge=1)


class Preferences(_Model):
    target_roles: tuple[NonEmptyStr, ...] = Field(min_length=1)
    # Ordered highest priority first; keys are free-form tier names.
    sourcing_hierarchy: dict[str, MarketTier] = Field(min_length=1)
    excluded_employers: tuple[NonEmptyStr, ...] = ()
    cv_page_budget_rules: PageBudget


class Skill(_Model):
    name: NonEmptyStr
    proficiency: Literal["beginner", "intermediate", "advanced", "expert"]
    years_of_experience: float = Field(ge=0)
    last_used_year: int | None = None
