"""`job-butler scout`: discover, list, and re-verify job postings."""

from typing import Annotated

import httpx
import typer

from src.cli_common import db_session, friendly_errors, profile_loader, progress_bars, tier_labels
from src.config.settings import Settings
from src.ingestion.firecrawl_client import FirecrawlClient
from src.services import scout as scout_service

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
    with _http() as http, db_session() as session:
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
        with progress_bars() as progress:
            report = scout_service.sweep(
                profile, session, http, firecrawl, limit=limit, progress=progress
            )
    typer.echo(
        f"[✓] Discovered {report.discovered}: excluded {report.excluded}, "
        f"duplicates {report.duplicates}, stale {report.stale}, "
        f"rejected {report.rejected}{_gates(report.rejected_by)}, "
        f"closed {report.closed}, saved {report.saved} ({report.new} new); "
        f"pruned {report.pruned} stored"
    )
    for error in report.errors:
        typer.echo(f"[!] {error}")


def _gates(rejected_by: dict[str, int]) -> str:
    return (
        f" ({', '.join(f'{g} {n}' for g, n in sorted(rejected_by.items()))})" if rejected_by else ""
    )


def _cell(value: str, width: int) -> str:
    return (value if len(value) <= width else value[: width - 1] + "…").ljust(width)


@scout_app.command("list")
def list_jobs(
    min_score: Annotated[int | None, typer.Option(help="Hide jobs scoring below this.")] = None,
) -> None:
    """Show active jobs, best fit first."""
    with db_session() as session:
        jobs = scout_service.list_jobs(session, min_score=min_score)
    if not jobs:
        typer.echo("No active jobs yet. Run `job-butler scout run`.")
        return
    labels = tier_labels()
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
def prune(
    job_id: Annotated[str | None, typer.Option(help="Remove one job for good.")] = None,
) -> None:
    """Deactivate jobs failing a profile gate or older than job_max_age (or one job)."""
    with db_session() as session:
        if job_id:
            try:
                row = scout_service.prune_one(session, job_id)
            except scout_service.ScoutError as exc:
                typer.echo(f"[✗] {exc}")
                raise typer.Exit(1) from None
            typer.echo(f"[✓] Pruned {row.id}: {row.title} at {row.company}")
            return
        with friendly_errors():
            profile = profile_loader().load()
        typer.echo(f"[✓] Pruned {scout_service.prune(session, profile)} job(s)")


@scout_app.command()
def verify(
    delete_closed: Annotated[
        bool,
        typer.Option(
            "--delete-closed",
            help="Delete closed jobs from the database instead of deactivating them",
        ),
    ] = False,
) -> None:
    """Re-check every active job's link; closed postings are deactivated (or deleted)."""
    with friendly_errors():
        profile = profile_loader().load()
    with _http() as http, db_session() as session, progress_bars() as progress:
        pruned, counts = scout_service.verify(
            session, http, profile, progress=progress, delete_closed=delete_closed
        )
    typer.echo(f"[✓] Pruned {pruned} stored job(s) that no longer fit the profile")
    summary = ", ".join(f"{status} {n}" for status, n in counts.items())
    typer.echo(f"[✓] Verified: {summary}")


@scout_app.command("format")
def format_cmd() -> None:
    """Format stored job descriptions into structured sections and bullet lists."""
    with db_session() as session:
        count = scout_service.format_descriptions(session)
    typer.echo(f"[✓] Formatted {count} stored job description(s)")
