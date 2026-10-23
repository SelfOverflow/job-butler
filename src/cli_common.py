"""Helpers shared by the `job-butler` command groups."""

from collections.abc import Iterator
from contextlib import contextmanager

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from sqlalchemy.orm import Session

from src.config.settings import Settings
from src.ingestion.base import ProgressFn
from src.profile.loader import ProfileError, ProfileLoader
from src.storage.database import init_db, make_engine, session_factory


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


@contextmanager
def db_session() -> Iterator[Session]:
    engine = make_engine(Settings().database_url)
    init_db(engine)
    try:
        with session_factory(engine)() as session:
            yield session
    finally:
        engine.dispose()


STAGES = {
    "search": "Searching Firecrawl",
    "boards": "Fetching company boards",
    "linkedin": "Searching LinkedIn",
    "resolve": "Resolving employers",
    "verify": "Verifying links",
    "tailor": "Tailoring resumes",
}


@contextmanager
def progress_bars() -> Iterator[ProgressFn]:
    """One live bar per pipeline stage, on stderr so stdout stays scriptable."""
    columns = (
        SpinnerColumn(),
        TextColumn("{task.description:<24}"),
        BarColumn(bar_width=30),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TextColumn("[dim]{task.fields[detail]}"),
    )
    with Progress(*columns, console=Console(stderr=True)) as bars:
        tasks: dict[str, TaskID] = {}

        def update(stage: str, done: int, total: int, detail: str) -> None:
            if stage not in tasks:
                tasks[stage] = bars.add_task(STAGES.get(stage, stage), total=total, detail="")
            short = detail if len(detail) <= 50 else detail[:49] + "…"
            bars.update(tasks[stage], completed=done, total=total, detail=short)

        yield update


def tier_labels() -> dict[str, str]:
    """Map tier keys to `Tier N` by profile order; empty if the profile can't load."""
    try:
        hierarchy = profile_loader().load().preferences.sourcing_hierarchy
    except Exception:  # Listing must work even with a broken profile.
        return {}
    return {name: f"Tier {i}" for i, name in enumerate(hierarchy, start=1)}
