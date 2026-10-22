"""`job-butler` command-line entrypoint."""

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from src.config.settings import Settings
from src.profile.exporter import to_markdown
from src.profile.loader import ProfileError, ProfileLoader
from src.profile.screening import resolve
from src.profile.updater import ProfileUpdater

app = typer.Typer(no_args_is_help=True, help="Job Butler: autonomous job search assistant.")
profile_app = typer.Typer(no_args_is_help=True, help="Manage the candidate profile.")
app.add_typer(profile_app, name="profile")


def _loader() -> ProfileLoader:
    return ProfileLoader(Settings().profile_path)


def _updater() -> ProfileUpdater:
    loader = _loader()
    return ProfileUpdater(loader, loader.path.parent / "backups")


@contextmanager
def _friendly_errors() -> Iterator[None]:
    """Turn profile errors into readable output and a non-zero exit code."""
    try:
        yield
    except ProfileError as exc:
        typer.echo(f"[✗] {exc}")
        raise typer.Exit(1) from None
    except ValidationError as exc:
        typer.echo(f"[✗] Profile invalid ({exc.error_count()} error(s)):")
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"]) or "<root>"
            typer.echo(f"    {location}: {error['msg']}")
        raise typer.Exit(1) from None


@profile_app.command()
def init(
    template: Annotated[Path, typer.Option(help="Template to copy.")] = Path(
        "profile/candidate_profile.template.yaml"
    ),
    force: Annotated[bool, typer.Option(help="Overwrite an existing profile.")] = False,
) -> None:
    """Scaffold a new profile from the template."""
    target = Settings().profile_path
    if target.exists() and not force:
        typer.echo(f"[✗] {target} already exists (use --force to overwrite).")
        raise typer.Exit(1)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template, target)
    typer.echo(f"[✓] Scaffolded {target} from {template}. Ready to edit!")


@profile_app.command()
def validate() -> None:
    """Validate the profile and print a summary."""
    with _friendly_errors():
        profile = _loader().load()
    typer.echo(
        f"[✓] Profile valid: {profile.personal_info.full_name} "
        f"({len(profile.bullets)} atomic bullets, {len(profile.work_experience)} roles, "
        f"{len(profile.star_stories)} STAR stories, "
        f"{len(profile.screening_question_bank)} screening answers registered)"
    )


@profile_app.command()
def query(question: str) -> None:
    """Answer a screening question from the profile's question bank."""
    with _friendly_errors():
        profile = _loader().load()
    match = resolve(question, profile.screening_question_bank)
    if match is None:
        typer.echo("[?] No matching screening answer.")
        raise typer.Exit(1)
    value = match.answer_value
    typer.echo(("Yes" if value else "No") if isinstance(value, bool) else str(value))


@profile_app.command()
def update(
    assignments: Annotated[
        list[str],
        typer.Option("--set", help="PATH=VALUE, e.g. preferences.currency=INR (repeatable)."),
    ],
) -> None:
    """Set profile values; all assignments are validated and saved together."""
    pairs = []
    for assignment in assignments:
        path, sep, value = assignment.partition("=")
        if not sep or not path:
            typer.echo(f"[✗] Expected PATH=VALUE, got {assignment!r}")
            raise typer.Exit(1)
        pairs.append((path, value))
    with _friendly_errors():
        _updater().set_values(pairs)
    typer.echo(f"[✓] Updated {', '.join(p for p, _ in pairs)} (previous version backed up)")


@profile_app.command("add-bullet")
def add_bullet(
    role_id: Annotated[str, typer.Option(help="work_experience id to append to.")],
    text: Annotated[str, typer.Option(help="The verified claim.")],
    skills: Annotated[str, typer.Option(help="Comma-separated skills.")] = "",
) -> None:
    """Append a verified atomic bullet to a role."""
    skill_list = [s.strip() for s in skills.split(",") if s.strip()]
    with _friendly_errors():
        bullet = _updater().add_bullet(role_id, text, skill_list)
    typer.echo(f"[✓] Added bullet {bullet.id} to {role_id}")


@profile_app.command()
def backups() -> None:
    """List profile backups, oldest first."""
    found = _updater().list_backups()
    if not found:
        typer.echo("No backups yet.")
    for path in found:
        typer.echo(path.name)


@profile_app.command()
def restore(name: Annotated[str, typer.Argument(help="Backup file name from `backups`.")]) -> None:
    """Restore the profile from a backup (the current version is backed up first)."""
    updater = _updater()
    match = next((p for p in updater.list_backups() if p.name == name), None)
    if match is None:
        typer.echo(f"[✗] No such backup: {name}")
        raise typer.Exit(1)
    with _friendly_errors():
        updater.restore(match)
    typer.echo(f"[✓] Restored {updater.loader.path} from {name}")


@profile_app.command("export-master")
def export_master(
    output: Annotated[
        Path | None, typer.Option(help="Defaults to <artifacts>/master_resume.md")
    ] = None,
) -> None:
    """Write the full profile as a Markdown master resume."""
    with _friendly_errors():
        profile = _loader().load()
    target = output or Settings().artifacts_dir / "master_resume.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(to_markdown(profile), encoding="utf-8")
    typer.echo(f"[✓] Master resume written to {target}")
