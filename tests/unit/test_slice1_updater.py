from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.profile.loader import ProfileError, ProfileLoader
from src.profile.updater import ProfileUpdater

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = REPO_ROOT / "profile" / "candidate_profile.template.yaml"
ENV = {
    "CANDIDATE_PHONE": "+1 555 0100",
    "CANDIDATE_CITY": "Springfield",
    "CANDIDATE_STATE": "State",
    "CANDIDATE_POSTAL_CODE": "00000",
}
NOW = datetime(2026, 10, 22, 9, 30, 15)


@pytest.fixture
def profile_path(tmp_path: Path) -> Path:
    path = tmp_path / "candidate_profile.yaml"
    path.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    return path


@pytest.fixture
def updater(profile_path: Path, tmp_path: Path) -> ProfileUpdater:
    loader = ProfileLoader(profile_path, env=ENV)
    return ProfileUpdater(loader, tmp_path / "backups", clock=lambda: NOW)


def test_profile_updater_creates_backup_on_mutation(
    updater: ProfileUpdater, profile_path: Path
) -> None:
    before = profile_path.read_text(encoding="utf-8")
    profile = updater.set_value("preferences.target_roles", '["Staff Engineer", "Tech Lead"]')

    assert profile.preferences.target_roles == ("Staff Engineer", "Tech Lead")
    assert updater.loader.snapshot().preferences.target_roles == ("Staff Engineer", "Tech Lead")
    backups = updater.list_backups()
    assert [b.name for b in backups] == ["candidate_profile_20261022_093015.yaml"]
    assert backups[0].read_text(encoding="utf-8") == before


def test_save_preserves_placeholders_comments_and_formatting(
    updater: ProfileUpdater, profile_path: Path
) -> None:
    before = profile_path.read_text(encoding="utf-8")
    updater.set_value("personal_info.full_name", '"Jane Doe"')  # same value: no-op edit
    after = profile_path.read_text(encoding="utf-8")
    assert after == before
    assert "${CANDIDATE_PHONE}" in after
    assert "# Full verbatim URL" in after


def test_set_value_parses_scalars_and_list_indices(updater: ProfileUpdater) -> None:
    profile = updater.set_value("work_experience.1.title", "Staff Engineer")
    assert profile.work_experience[1].title == "Staff Engineer"
    profile = updater.set_value("preferences.cv_page_budget_rules.international", "3")
    assert profile.preferences.cv_page_budget_rules.international == 3


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("personal_info.email", "not-an-email"),
        ("personal_info.full_name", "null"),
        ("preferences.min_base_salary", "180000"),  # not in schema
        ("work_experience", "[]"),
    ],
)
def test_profile_updater_rejects_invalid_mutation(
    updater: ProfileUpdater, profile_path: Path, path: str, value: str
) -> None:
    before = profile_path.read_text(encoding="utf-8")
    with pytest.raises(ValidationError):
        updater.set_value(path, value)
    assert profile_path.read_text(encoding="utf-8") == before
    assert updater.list_backups() == []


@pytest.mark.parametrize(
    "path", ["work_experience.9.title", "personal_info.full_name.first", "", "a..b"]
)
def test_set_value_rejects_bad_paths(updater: ProfileUpdater, path: str) -> None:
    with pytest.raises(ProfileError):
        updater.set_value(path, "x")


def test_add_bullet_generates_hashed_id(updater: ProfileUpdater) -> None:
    role_id = updater.loader.snapshot().work_experience[1].id
    bullet = updater.add_bullet(role_id, "Cut build times by 40% with remote caching.", ["Bazel"])

    assert bullet.id == f"b_{bullet.fact_hash[:8]}"
    role = updater.loader.snapshot().work_experience[1]
    assert role.atomic_bullets[-1] == bullet
    assert bullet.skills == ("Bazel",)


def test_add_bullet_rejects_unknown_role_and_duplicate_claim(updater: ProfileUpdater) -> None:
    with pytest.raises(ProfileError, match="Unknown role"):
        updater.add_bullet("exp_missing", "Anything.", [])
    role_id = updater.loader.snapshot().work_experience[0].id
    updater.add_bullet(role_id, "Shipped a thing.", [])
    with pytest.raises(ValidationError, match="Duplicate atomic bullet id"):
        updater.add_bullet(role_id, "Shipped  a thing.", [])  # same claim, extra whitespace


def test_backup_names_never_collide(updater: ProfileUpdater) -> None:
    updater.set_value("work_experience.0.title", "A")
    updater.set_value("work_experience.0.title", "B")
    names = [b.name for b in updater.list_backups()]
    assert names == [
        "candidate_profile_20261022_093015.yaml",
        "candidate_profile_20261022_093015_1.yaml",
    ]


def test_restore_backup(updater: ProfileUpdater, profile_path: Path) -> None:
    original = profile_path.read_text(encoding="utf-8")
    updater.set_value("work_experience.0.title", "Changed")
    first_backup = updater.list_backups()[0]

    profile = updater.restore(first_backup)
    assert profile.work_experience[0].title == "Senior Backend Engineer"
    assert profile_path.read_text(encoding="utf-8") == original
    assert len(updater.list_backups()) == 2  # the pre-restore state is backed up too


def test_failed_write_leaves_profile_intact(
    updater: ProfileUpdater, profile_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = profile_path.read_text(encoding="utf-8")
    monkeypatch.setattr("src.profile.updater.os.replace", _raise_disk_full)
    with pytest.raises(OSError, match="disk full"):
        updater.set_value("work_experience.0.title", "Changed")
    assert profile_path.read_text(encoding="utf-8") == before
    assert sorted(p.name for p in profile_path.parent.iterdir()) == ["backups", profile_path.name]


def _raise_disk_full(*_: object) -> None:
    raise OSError("disk full")
