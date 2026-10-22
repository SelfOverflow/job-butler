import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.profile.loader import ProfileError, ProfileLoader, interpolate

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = REPO_ROOT / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "Springfield",
    "CANDIDATE_STATE": "State",
    "CANDIDATE_POSTAL_CODE": "00000",
}


@pytest.fixture
def profile_path(tmp_path: Path) -> Path:
    path = tmp_path / "candidate_profile.yaml"
    path.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def test_interpolate_resolves_vars_defaults_and_nested_values() -> None:
    data = {
        "a": "${X}",
        "b": ["pre-${X}-${Y}", 5, None],
        "c": {"d": "${MISSING:-fallback}", "e": "${EMPTY:-fallback}"},
    }
    env = {"X": "1", "Y": "2", "EMPTY": ""}
    assert interpolate(data, env) == {
        "a": "1",
        "b": ["pre-1-2", 5, None],
        "c": {"d": "fallback", "e": "fallback"},
    }


def test_interpolate_reports_all_missing_vars() -> None:
    with pytest.raises(ProfileError, match="CANDIDATE_CITY, CANDIDATE_PHONE"):
        interpolate({"phone": "${CANDIDATE_PHONE}", "city": "${CANDIDATE_CITY}"}, {})


def test_profile_loader_env_variable_interpolation(profile_path: Path) -> None:
    profile = ProfileLoader(profile_path, env=ENV).load()
    assert profile.personal_info.phone == "+1 555 0100"
    assert profile.personal_info.location.city == "Springfield"
    # Template uses ${CANDIDATE_EMAIL:-jane.doe@example.com}
    assert profile.personal_info.email == "jane.doe@example.com"


def test_loader_reads_dotenv_and_process_env_wins(
    profile_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    lines = [f'{k}="{v}"' for k, v in ENV.items()] + ['CANDIDATE_EMAIL="dotenv@example.com"']
    env_file.write_text("\n".join(lines), encoding="utf-8")
    monkeypatch.delenv("CANDIDATE_CITY", raising=False)
    monkeypatch.setenv("CANDIDATE_EMAIL", "shell@example.com")

    profile = ProfileLoader(profile_path, env_file=env_file).load()
    assert profile.personal_info.location.city == "Springfield"
    assert profile.personal_info.email == "shell@example.com"


def test_loader_accepts_json(profile_path: Path, tmp_path: Path) -> None:
    json_path = tmp_path / "profile.json"
    json_path.write_text(json.dumps(yaml.safe_load(profile_path.read_text())), encoding="utf-8")
    assert ProfileLoader(json_path, env=ENV).load().personal_info.full_name == "Jane Doe"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (None, "not found"),
        ("personal_info: [unclosed", "Invalid YAML"),
        ("- just\n- a list\n", "must be a mapping"),
    ],
)
def test_loader_errors_are_readable(tmp_path: Path, content: str | None, message: str) -> None:
    path = tmp_path / "candidate_profile.yaml"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    with pytest.raises(ProfileError, match=message):
        ProfileLoader(path, env=ENV).load()


def test_loader_propagates_schema_errors(profile_path: Path) -> None:
    profile_path.write_text(
        profile_path.read_text().replace('full_name: "Jane Doe"', 'full_name: ""'),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        ProfileLoader(profile_path, env=ENV).load()


def test_snapshot_is_independent_copy_and_survives_bad_edits(profile_path: Path) -> None:
    loader = ProfileLoader(profile_path, env=ENV)
    snap = loader.snapshot()  # loads on first use
    tier = next(iter(snap.preferences.sourcing_hierarchy))
    snap.preferences.sourcing_hierarchy.pop(tier)  # dicts stay mutable; copies must not leak
    assert tier in loader.snapshot().preferences.sourcing_hierarchy

    profile_path.write_text("personal_info: [unclosed", encoding="utf-8")
    with pytest.raises(ProfileError):
        loader.load()
    assert loader.snapshot().personal_info.full_name == "Jane Doe"


def test_load_picks_up_edits(profile_path: Path) -> None:
    loader = ProfileLoader(profile_path, env=ENV)
    assert loader.load().personal_info.full_name == "Jane Doe"
    profile_path.write_text(
        profile_path.read_text().replace('"Jane Doe"', '"John Roe"'), encoding="utf-8"
    )
    assert loader.load().personal_info.full_name == "John Roe"
    assert loader.snapshot().personal_info.full_name == "John Roe"
