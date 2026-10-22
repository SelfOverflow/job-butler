"""`job-butler` command-line entrypoint."""

from pathlib import Path
from typing import Annotated

import typer

from src.cli_analytics import analytics_app
from src.cli_apply import apply_app
from src.cli_autopilot import autopilot_app
from src.cli_common import friendly_errors, profile_loader
from src.cli_scout import scout_app
from src.cli_tailor import tailor_app
from src.config.settings import Settings
from src.profile.updater import ProfileUpdater
from src.services import profile as profile_service

app = typer.Typer(no_args_is_help=True, help="Job Butler: autonomous job search assistant.")
profile_app = typer.Typer(no_args_is_help=True, help="Manage the candidate profile.")
app.add_typer(profile_app, name="profile")
app.add_typer(scout_app, name="scout")
app.add_typer(tailor_app, name="tailor")
app.add_typer(apply_app, name="apply")
app.add_typer(analytics_app, name="analytics")
app.add_typer(autopilot_app, name="autopilot")


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Interface to bind.")] = "127.0.0.1",
    port: Annotated[int | None, typer.Option(help="Defaults to PORT (8000).")] = None,
) -> None:
    """Run the dashboard and REST API on one port."""
    import uvicorn

    from src.server.app import FRONTEND_OUT, create_app

    bind = port or Settings().port
    typer.echo(f"[✓] Job Butler dashboard & API: http://{host}:{bind}")
    if not FRONTEND_OUT.is_dir():
        typer.echo("[!] frontend/out not built yet: API only (cd frontend && npm run build)")
    uvicorn.run(create_app(), host=host, port=bind)


def _updater() -> ProfileUpdater:
    loader = profile_loader()
    return ProfileUpdater(loader, loader.path.parent / "backups")


@profile_app.command()
def init(
    template: Annotated[Path, typer.Option(help="Template to copy.")] = Path(
        "profile/candidate_profile.template.yaml"
    ),
    force: Annotated[bool, typer.Option(help="Overwrite an existing profile.")] = False,
) -> None:
    """Scaffold a new profile from the template."""
    with friendly_errors():
        target = profile_service.init_profile(template, Settings().profile_path, force=force)
    typer.echo(f"[✓] Scaffolded {target} from {template}. Ready to edit!")


@profile_app.command()
def validate() -> None:
    """Validate the profile and print a summary."""
    with friendly_errors():
        summary = profile_service.validate_profile(profile_loader())
    typer.echo(
        f"[✓] Profile valid: {summary.full_name} "
        f"({summary.bullet_count} atomic bullets, {summary.role_count} roles, "
        f"{summary.star_story_count} STAR stories, "
        f"{summary.screening_count} screening answers registered)"
    )


@profile_app.command()
def query(question: str) -> None:
    """Answer a screening question from the profile's question bank."""
    with friendly_errors():
        profile = profile_loader().load()
        value = profile_service.query_screening(profile, question)
    typer.echo(("Yes" if value else "No") if isinstance(value, bool) else str(value))


@profile_app.command()
def update(
    assignments: Annotated[
        list[str],
        typer.Option("--set", help="PATH=VALUE, e.g. preferences.currency=INR (repeatable)."),
    ],
) -> None:
    """Set profile values; all assignments are validated and saved together."""
    with friendly_errors():
        pairs = profile_service.update_profile(_updater(), assignments)
    typer.echo(f"[✓] Updated {', '.join(p for p, _ in pairs)} (previous version backed up)")


@profile_app.command("add-bullet")
def add_bullet(
    role_id: Annotated[str, typer.Option(help="work_experience id to append to.")],
    text: Annotated[str, typer.Option(help="The verified claim.")],
    skills: Annotated[str, typer.Option(help="Comma-separated skills.")] = "",
) -> None:
    """Append a verified atomic bullet to a role."""
    skill_list = [s.strip() for s in skills.split(",") if s.strip()]
    with friendly_errors():
        bullet_id = profile_service.add_bullet(_updater(), role_id, text, skill_list)
    typer.echo(f"[✓] Added bullet {bullet_id} to {role_id}")


@profile_app.command()
def backups() -> None:
    """List profile backups, oldest first."""
    found = profile_service.list_backups(_updater())
    if not found:
        typer.echo("No backups yet.")
    for path in found:
        typer.echo(path.name)


@profile_app.command()
def restore(name: Annotated[str, typer.Argument(help="Backup file name from `backups`.")]) -> None:
    """Restore the profile from a backup (the current version is backed up first)."""
    with friendly_errors():
        target = profile_service.restore_backup(_updater(), name)
    typer.echo(f"[✓] Restored {target} from {name}")


@profile_app.command("export-master")
def export_master(
    output: Annotated[
        Path | None, typer.Option(help="Defaults to <artifacts>/master_resume.md")
    ] = None,
) -> None:
    """Write the full profile as a Markdown master resume."""
    with friendly_errors():
        profile = profile_loader().load()
        target = output or Settings().artifacts_dir / "master_resume.md"
        profile_service.export_master(profile, target)
    typer.echo(f"[✓] Master resume written to {target}")
