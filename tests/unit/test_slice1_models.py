import copy
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from src.config.settings import Settings
from src.profile.models import CandidateProfile, PersonalInfo, Preferences, Skill, STARStory

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE_FILES = ["candidate_profile.yaml", "candidate_profile.template.yaml"]

# Stand-ins for the ${VAR} placeholders the loader will resolve in a later increment.
ENV_VALUES = {
    "${CANDIDATE_EMAIL}": "jane@example.com",
    "${CANDIDATE_EMAIL:-jane.doe@example.com}": "jane.doe@example.com",
    "${CANDIDATE_PHONE}": "+1 555 0100",
    "${CANDIDATE_CITY}": "Springfield",
    "${CANDIDATE_STATE}": "State",
    "${CANDIDATE_POSTAL_CODE}": "00000",
}


def _resolve(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _resolve(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_resolve(v) for v in node]
    return ENV_VALUES.get(node, node) if isinstance(node, str) else node


def _raw(name: str = "candidate_profile.template.yaml") -> dict[str, Any]:
    data = yaml.safe_load((REPO_ROOT / "profile" / name).read_text(encoding="utf-8"))
    resolved: dict[str, Any] = _resolve(data)
    return resolved


def test_settings_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("APP_ENV", "DATABASE_URL", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    defaults = Settings(_env_file=None)
    assert defaults.app_env == "local"
    assert defaults.database_url == "sqlite:///./data/job_butler.db"
    assert defaults.artifacts_dir == Path("artifacts")
    assert defaults.gemini_api_key is None

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    configured = Settings(_env_file=None)
    assert configured.app_env == "production"
    assert configured.gemini_api_key == "g-key"


@pytest.mark.parametrize("name", PROFILE_FILES)
def test_profile_sections_valid(name: str) -> None:
    raw = _raw(name)
    info = PersonalInfo.model_validate(raw["personal_info"])
    prefs = Preferences.model_validate(raw["preferences"])
    skills = [Skill.model_validate(s) for group in raw["skills_inventory"].values() for s in group]

    assert info.full_name == raw["personal_info"]["full_name"]
    assert info.links.linkedin == raw["personal_info"]["links"]["linkedin"]
    assert prefs.excluded_employers and prefs.target_roles
    assert list(prefs.sourcing_hierarchy) == list(raw["preferences"]["sourcing_hierarchy"])
    assert prefs.cv_page_budget_rules.domestic == 1
    assert skills


def test_profile_is_immutable() -> None:
    info = PersonalInfo.model_validate(_raw()["personal_info"])
    with pytest.raises(ValidationError):
        info.full_name = "Someone Else"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [("email", "not-an-email"), ("full_name", "  ")],
)
def test_invalid_personal_info_rejected(field: str, value: str) -> None:
    raw = _raw()["personal_info"]
    raw[field] = value
    with pytest.raises(ValidationError):
        PersonalInfo.model_validate(raw)


def test_linkedin_must_be_full_url() -> None:
    raw = _raw()["personal_info"]
    raw["links"]["linkedin"] = "linkedin.com/in/janedoe"
    with pytest.raises(ValidationError):
        PersonalInfo.model_validate(raw)


def test_unknown_field_rejected() -> None:
    raw = _raw()["preferences"]
    raw["excluded_employer"] = ["Typo Corp"]
    with pytest.raises(ValidationError):
        Preferences.model_validate(raw)


def test_invalid_skill_proficiency_rejected() -> None:
    with pytest.raises(ValidationError):
        Skill.model_validate({"name": "Go", "proficiency": "guru", "years_of_experience": 1})


@pytest.mark.parametrize("name", PROFILE_FILES)
def test_candidate_profile_valid(name: str) -> None:
    raw = _raw(name)
    profile = CandidateProfile.model_validate(raw)

    assert [r.id for r in profile.work_experience] == [r["id"] for r in raw["work_experience"]]
    for role, raw_role in zip(profile.work_experience, raw["work_experience"], strict=True):
        assert [b.text for b in role.atomic_bullets] == [
            b["text"] for b in raw_role["atomic_bullets"]
        ]
    assert len(profile.bullets) == sum(len(r["atomic_bullets"]) for r in raw["work_experience"])
    assert len(profile.star_stories) == len(raw["star_stories"])
    assert len(profile.screening_question_bank) == len(raw["screening_question_bank"])


def test_bullet_fact_hash_is_deterministic_and_text_sensitive() -> None:
    bullet = CandidateProfile.model_validate(_raw()).bullets[0]
    again = CandidateProfile.model_validate(_raw()).bullets[0]
    assert bullet.fact_hash == again.fact_hash
    assert len(bullet.fact_hash) == 64

    edited = bullet.model_copy(update={"text": bullet.text + " Extra."})
    assert edited.fact_hash != bullet.fact_hash


def test_candidate_profile_duplicate_bullet_ids_rejected() -> None:
    raw = _raw()
    duplicate = copy.deepcopy(raw["work_experience"][0]["atomic_bullets"][0])
    raw["work_experience"][1]["atomic_bullets"].append(duplicate)
    with pytest.raises(ValidationError, match="Duplicate atomic bullet id"):
        CandidateProfile.model_validate(raw)


def test_duplicate_role_ids_rejected() -> None:
    raw = _raw()
    raw["work_experience"][1]["id"] = raw["work_experience"][0]["id"]
    with pytest.raises(ValidationError, match="Duplicate work_experience id"):
        CandidateProfile.model_validate(raw)


def test_empty_work_experience_rejected() -> None:
    raw = _raw()
    raw["work_experience"] = []
    with pytest.raises(ValidationError):
        CandidateProfile.model_validate(raw)


@pytest.mark.parametrize(
    ("start", "end", "is_current"),
    [
        ("2023/01", None, True),  # wrong date format
        ("2023-05", "2023-01", False),  # end before start
        ("2023-01", "2023-05", True),  # current role with an end date
        ("2023-01", None, False),  # past role without an end date
    ],
)
def test_invalid_role_dates_rejected(start: str, end: str | None, is_current: bool) -> None:
    raw = _raw()
    raw["work_experience"][0].update(start_date=start, end_date=end, is_current=is_current)
    with pytest.raises(ValidationError):
        CandidateProfile.model_validate(raw)


@pytest.mark.parametrize("missing", ["situation", "task", "action", "result"])
def test_star_stories_schema_validation(missing: str) -> None:
    story = {"id": "s1", "situation": "S", "task": "T", "action": "A", "result": "R"}
    STARStory.model_validate(story)
    del story[missing]
    with pytest.raises(ValidationError):
        STARStory.model_validate(story)


@pytest.mark.parametrize(
    ("answer_type", "answer_value"),
    [("boolean", "yes"), ("number", "five"), ("number", True), ("text", 5)],
)
def test_screening_answer_type_mismatch_rejected(answer_type: str, answer_value: Any) -> None:
    raw = _raw()
    raw["screening_question_bank"][0].update(answer_type=answer_type, answer_value=answer_value)
    with pytest.raises(ValidationError):
        CandidateProfile.model_validate(raw)


def test_invalid_screening_regex_rejected() -> None:
    raw = _raw()
    raw["screening_question_bank"][0]["question_pattern"] = "(unclosed"
    with pytest.raises(ValidationError):
        CandidateProfile.model_validate(raw)
