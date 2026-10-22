"""`job-butler scout`: discover, list, and re-verify job postings."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

import httpx
import typer
from sqlalchemy.orm import Session

from src.cli_common import friendly_errors, profile_loader
from src.config.settings import Settings
from src.ingestion.firecrawl_client import FirecrawlClient
from src.ingestion.pipeline import run_sweep, verify_stored
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory

scout_app = typer.Typer(no_args_is_help=True, help="Discover, list, and verify job postings.")
USER_AGENT = "job-butler/0.1 (+https://github.com/SelfOverflow/job-butler)"
COLUMNS = (
    ("ID", 12),
    ("Score", 5),
    ("Tier", 7),
    ("Company", 18),
    ("Title", 32),
    ("Location", 22),
    ("Active", 6),
    ("Source", 10),
)


@contextmanager
def _session() -> Iterator[Session]:
    engine = make_engine(Settings().database_url)
    init_db(engine)
    try:
        with session_factory(engine)() as session:
            yield session
    finally:
        engine.dispose()


def _http() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT})


@scout_app.command()
def run(
    limit: Annotated[
        int, typer.Option(help="Verify and save at most this many top-scored jobs.")
    ] = 20,
) -> None:
    """Discover jobs that fit the profile, verify the best ones, and save them."""
    settings = Settings()
    with friendly_errors():
        profile = profile_loader().load()
    with _http() as http, _session() as session:
        firecrawl = None
        if settings.firecrawl_api_key:
            firecrawl = FirecrawlClient(
                settings.firecrawl_api_key,
                http,
                settings.firecrawl_state_dir,
                daily_credits=settings.max_daily_scrape_credits,
            )
        else:
            typer.echo(
                "[!] FIRECRAWL_API_KEY not set: only preferences.watched_companies are scanned."
            )
        report = run_sweep(profile, session, http, firecrawl, limit=limit)
    typer.echo(
        f"[✓] Discovered {report.discovered}: excluded {report.excluded}, "
        f"duplicates {report.duplicates}, visa-rejected {report.rejected}, "
        f"closed {report.closed}, saved {report.saved} ({report.new} new)"
    )
    for error in report.errors:
        typer.echo(f"[!] {error}")


def _tier_labels() -> dict[str, str]:
    """Map tier keys to `Tier N` by profile order; empty if the profile can't load."""
    try:
        hierarchy = profile_loader().load().preferences.sourcing_hierarchy
    except Exception:  # Listing must work even with a broken profile.
        return {}
    return {name: f"Tier {i}" for i, name in enumerate(hierarchy, start=1)}


def _cell(value: str, width: int) -> str:
    return (value if len(value) <= width else value[: width - 1] + "…").ljust(width)


@scout_app.command("list")
def list_jobs(
    min_score: Annotated[int | None, typer.Option(help="Hide jobs scoring below this.")] = None,
) -> None:
    """Show active jobs, best fit first."""
    with _session() as session:
        jobs = repo.list_active(session, min_score=min_score)
    if not jobs:
        typer.echo("No active jobs yet. Run `job-butler scout run`.")
        return
    labels = _tier_labels()
    header = "  ".join(_cell(name, width) for name, width in COLUMNS)
    typer.echo(header.rstrip())
    typer.echo("-" * len(header.rstrip()))
    for job in jobs:
        tier = labels.get(job.tier, job.tier) if job.tier else "-"
        active = "[LIVE]" if job.last_verified_at else "[?]"
        values = (
            job.id,
            str(job.score),
            tier,
            job.company,
            job.title,
            job.location,
            active,
            job.source,
        )
        typer.echo(
            "  ".join(_cell(v, w) for v, (_, w) in zip(values, COLUMNS, strict=True)).rstrip()
        )


@scout_app.command()
def verify() -> None:
    """Re-check every active job's link; closed postings are deactivated."""
    with _http() as http, _session() as session:
        counts = verify_stored(session, http)
    summary = ", ".join(f"{status} {n}" for status, n in counts.items())
    typer.echo(f"[✓] Verified: {summary}")
