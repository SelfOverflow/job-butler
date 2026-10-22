"""`job-butler analytics report`: market trends, pipeline funnel, upskilling ROI."""

from collections import Counter
from typing import Annotated

import typer

from src.agents.tailor.runner import artifact_paths
from src.cli_common import db_session
from src.config.settings import Settings
from src.storage import repository as repo

analytics_app = typer.Typer(no_args_is_help=True, help="Hiring trends and upskilling insights.")
RULE = "=" * 76


@analytics_app.command()
def report(top: Annotated[int, typer.Option(help="Rows per section.")] = 5) -> None:
    """Print the latest market snapshot and your application funnel."""
    with db_session() as session:
        snapshot = repo.latest_market_snapshot(session)
        if snapshot is None:
            typer.echo("No market snapshot yet: run `job-butler scout run` first.")
            return
        active = repo.list_active(session)
        artifacts = Settings().artifacts_dir
        tailored = sum(artifact_paths(artifacts, j.id).resume.is_file() for j in active)
        statuses = Counter(a.status for a in repo.list_applications(session))

    apps = ", ".join(f"{n} {s.replace('_', ' ')}" for s, n in sorted(statuses.items())) or "none"
    typer.echo(f"{' Career Intelligence Report ':=^76}")
    typer.echo(f"Snapshot: {snapshot.created_at:%Y-%m-%d %H:%M} UTC")
    typer.echo(
        f"Market: {snapshot.total} eligible postings | {snapshot.matched} matched "
        f"(fit score >= {snapshot.threshold})"
    )
    typer.echo(f"Pipeline: {len(active)} active jobs | {tailored} tailored | applications: {apps}")
    demand = [
        f"{d['skill']} {d['share']:.0f}% {'✓' if d['have'] else '✗'}" for d in snapshot.demand[:top]
    ]
    typer.echo(f"Top demanded tech: {', '.join(demand)}")
    typer.echo("Top upskilling ROI:")
    if not snapshot.upskill:
        typer.echo("  No missing skill would unlock additional matches.")
    for i, u in enumerate(snapshot.upskill[:top], start=1):
        typer.echo(
            f"  {i}. {u['skill']}: unlocks {u['unlocks']} roles "
            f"(+{u['uplift_pct']}% vs {snapshot.matched} matched; in {u['demand']} postings)"
        )
    typer.echo(RULE)
