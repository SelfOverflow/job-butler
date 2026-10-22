"""Helpers shared by the `job-butler` command groups."""

from collections.abc import Iterator
from contextlib import contextmanager

import typer
from pydantic import ValidationError

from src.config.settings import Settings
from src.profile.loader import ProfileError, ProfileLoader


def profile_loader() -> ProfileLoader:
    return ProfileLoader(Settings().profile_path)


@contextmanager
def friendly_errors() -> Iterator[None]:
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
