"""`job-butler` command-line entrypoint."""

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from src.config.settings import Settings
from src.profile.loader import ProfileError, ProfileLoader
from src.profile.screening import resolve

app = typer.Typer(no_args_is_help=True, help="Job Butler: autonomous job search assistant.")
profile_app = typer.Typer(no_args_is_help=True, help="Manage the candidate profile.")
app.add_typer(profile_app, name="profile")


def _loader() -> ProfileLoader:
    return ProfileLoader(Settings().profile_path)


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
