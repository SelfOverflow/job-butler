"""`job-butler autopilot`: run sweep -> tailor -> prepare on an interval."""

from typing import Annotated

import typer

from src.cli_common import profile_loader
from src.config.settings import Settings
from src.scheduler.autopilot import Autopilot, CycleReport
from src.scheduler.stages import AutopilotLimits, build_stages
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory

autopilot_app = typer.Typer(no_args_is_help=True, help="24/7 autopilot (prepares, never submits).")


@autopilot_app.command()
def start(
    interval: Annotated[float, typer.Option(help="Minutes between cycles.")] = 60,
    once: Annotated[bool, typer.Option(help="Run a single cycle and exit.")] = False,
    sweep_limit: Annotated[int, typer.Option(help="Jobs verified and saved per sweep.")] = 20,
    tailor_per_cycle: Annotated[int, typer.Option(help="Resumes tailored per cycle.")] = 3,
    prepare_per_cycle: Annotated[int, typer.Option(help="Applications prepared per cycle.")] = 3,
    min_score: Annotated[int, typer.Option(help="Minimum fit score to tailor/prepare.")] = 75,
) -> None:
    """Run the autopilot in the foreground (Ctrl-C to stop). Applications are never submitted."""
    settings = Settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    sessions = session_factory(engine)
    limits = AutopilotLimits(sweep_limit, tailor_per_cycle, prepare_per_cycle, min_score)
    pilot = Autopilot(
        profile_loader(),
        sessions,
        build_stages(settings, sessions, limits),
        interval_minutes=interval,
    )
    cycle = 0

    def show(report: CycleReport) -> None:
        nonlocal cycle
        cycle += 1
        stages = " | ".join(f"{name}: {result}" for name, result in report.results.items())
        typer.echo(f"[{'✓' if report.ok else '!'}] Cycle {cycle}: {stages or 'no stages ran'}")
        for warning in report.warnings:
            typer.echo(f"    warning: {warning}")
        if not once:
            typer.echo(f"    next cycle in {pilot.next_delay() / 60:.0f} min")

    typer.echo("[✓] Autopilot started: applications are prepared for your review, never submitted.")
    try:
        pilot.run(max_cycles=1 if once else None, on_cycle=show)
    except KeyboardInterrupt:
        typer.echo("\nAutopilot stopped.")
    finally:
        engine.dispose()


@autopilot_app.command()
def status() -> None:
    """Show the most recent autopilot cycle."""
    engine = make_engine(Settings().database_url)
    init_db(engine)
    try:
        with session_factory(engine)() as session:
            events = repo.query_audit(session, action="AUTOPILOT_CYCLE", limit=1)
    finally:
        engine.dispose()
    if not events:
        typer.echo("No autopilot cycle has run yet. Start one with `job-butler autopilot start`.")
        return
    event = events[0]
    typer.echo(
        f"Last cycle: {event.timestamp:%Y-%m-%d %H:%M} UTC, {event.status}, {event.duration_ms} ms"
    )
    for name, result in event.details.get("stages", {}).items():
        typer.echo(f"    {name}: {result}")
    for warning in event.details.get("warnings", []):
        typer.echo(f"    warning: {warning}")
