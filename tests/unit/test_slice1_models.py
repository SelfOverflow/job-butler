from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from src.config.settings import Settings
from src.profile.models import PersonalInfo, Preferences, Skill

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
