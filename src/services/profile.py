"""Candidate profile service shared by the CLI and web API."""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.profile.exporter import to_markdown
from src.profile.loader import ProfileError, ProfileLoader
from src.profile.models import CandidateProfile
from src.profile.screening import resolve
from src.profile.updater import ProfileUpdater


@dataclass(frozen=True)
class ValidationSummary:
    full_name: str
    bullet_count: int
    role_count: int
    star_story_count: int
    screening_count: int
    profile: CandidateProfile


def init_profile(template: Path, target: Path, force: bool = False) -> Path:
    if target.exists() and not force:
        raise ProfileError(f"{target} already exists (use --force to overwrite).")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template, target)
    return target


def validate_profile(loader: ProfileLoader) -> ValidationSummary:
    profile = loader.load()
    return ValidationSummary(
        full_name=profile.personal_info.full_name,
        bullet_count=len(profile.bullets),
        role_count=len(profile.work_experience),
        star_story_count=len(profile.star_stories),
        screening_count=len(profile.screening_question_bank),
        profile=profile,
    )


def query_screening(profile: CandidateProfile, question: str) -> Any:
    match = resolve(question, profile.screening_question_bank)
    if match is None:
        raise ProfileError("No matching screening answer.")
    return match.answer_value


def update_profile(
    updater: ProfileUpdater, assignments: list[str] | list[tuple[str, str]]
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in assignments:
        if isinstance(item, tuple):
            pairs.append(item)
        else:
            path, sep, value = item.partition("=")
            if not sep or not path:
                raise ProfileError(f"Expected PATH=VALUE, got {item!r}")
            pairs.append((path, value))
    updater.set_values(pairs)
    return pairs


def add_bullet(updater: ProfileUpdater, role_id: str, text: str, skills: list[str]) -> str:
    bullet = updater.add_bullet(role_id, text, skills)
    return bullet.id


def list_backups(updater: ProfileUpdater) -> list[Path]:
    return updater.list_backups()


def restore_backup(updater: ProfileUpdater, name: str) -> Path:
    match = next((p for p in updater.list_backups() if p.name == name), None)
    if match is None:
        raise ProfileError(f"No such backup: {name}")
    updater.restore(match)
    return updater.loader.path


def export_master(profile: CandidateProfile, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(to_markdown(profile), encoding="utf-8")
    return target
