"""`job-butler apply`: prepare applications (never submits), review, approve, skip."""

from typing import Annotated

import typer

from src.agents.navigator.browser import BrowserBusyError
from src.cli_common import db_session, friendly_errors, profile_loader
from src.config.settings import Settings
from src.services import apply as service
from src.storage import repository as repo
from src.storage.models import PENDING_STATUSES, ApplicationRecord

apply_app = typer.Typer(help="Prepare applications for review, then approve to submit.")


def _fail(exc: Exception) -> typer.Exit:
    typer.echo(f"[✗] {exc}")
    return typer.Exit(1)


def _parse(answers: list[str]) -> dict[str, str]:
    parsed = {}
    for item in answers:
        question, sep, answer = item.partition("=")
        if not sep or not question.strip():
            raise _fail(ValueError(f"Expected QUESTION=ANSWER, got {item!r}"))
        parsed[question.strip()] = answer.strip()
    return parsed


def _report(record: ApplicationRecord) -> None:
    if record.status == "blocked":
        typer.echo(f"[!] Blocked: {record.barrier}. Finish it yourself, then `apply mark-applied`.")
    elif record.status == "needs_input":
        typer.echo(
            f"[!] Needs input: {len(record.questions)} question(s) the profile cannot answer:"
        )
        for question in record.questions:
            options = f" (options: {', '.join(question['options'])})" if question["options"] else ""
            typer.echo(f"    - {question['label']}{options}")
        typer.echo('    Answer with --answer "QUESTION=ANSWER" and run again.')
    elif record.status == "awaiting_review":
        typer.echo(f"[✓] Ready for review: {len(record.plan)} field(s) filled.")
        typer.echo(f"    Review, then submit with `job-butler apply approve {record.job_id}`.")
    elif record.status == "failed":
        typer.echo(f"[✗] Failed: {record.error}")
    if record.screenshot:
        typer.echo(f"    Screenshot: {record.screenshot}")


@apply_app.callback(invoke_without_command=True)
def apply(
    ctx: typer.Context,
    job_id: Annotated[str | None, typer.Option(help="Job to prepare an application for.")] = None,
    answer: Annotated[list[str] | None, typer.Option(help="QUESTION=ANSWER (repeatable).")] = None,
) -> None:
    """Fill an application from verified data for review. Never submits."""
    if ctx.invoked_subcommand is not None:
        return
    if not job_id:
        typer.echo(ctx.get_help())
        raise typer.Exit(1)
    answers = _parse(answer or [])
    with friendly_errors():
        profile = profile_loader().load()
    with db_session() as session:
        saved = repo.get_application(session, job_id)
        merged = {**(saved.answers if saved else {}), **answers}
        try:
            record = service.prepare(
                job_id,
                session=session,
                profile=profile,
                artifacts_dir=Settings().artifacts_dir,
                answers=merged,
            )
        except (service.ApplyError, BrowserBusyError) as exc:
            raise _fail(exc) from None
        _report(record)
    typer.echo("    Nothing was submitted.")


@apply_app.command("list")
def list_pending() -> None:
    """Applications waiting on you: needs input, blocked, or awaiting review."""
    with db_session() as session:
        pending = repo.list_applications(session, statuses=PENDING_STATUSES)
        if not pending:
            typer.echo("No pending applications.")
        for r in pending:
            typer.echo(f"{r.job_id}  {r.status:<16} {r.job.title} at {r.job.company}")


@apply_app.command()
def approve(
    job_id: str,
    yes: Annotated[
        bool, typer.Option("--yes", help="Submit without the confirmation prompt.")
    ] = False,
) -> None:
    """Show the reviewed answers and submit the application after confirmation."""
    with friendly_errors():
        profile = profile_loader().load()
    with db_session() as session:
        record = repo.get_application(session, job_id)
        if record is not None and record.status == "awaiting_review":
            typer.echo(f"{record.job.title} at {record.job.company}:")
            for field in record.plan:
                value = (
                    field["value"]
                    if field["kind"] not in ("file", "textarea")
                    else f"<{field['kind']}>"
                )
                typer.echo(f"    {field['label']}: {value}")
            if not yes and not typer.confirm(f"Submit this application to {record.job.company}?"):
                typer.echo("Not submitted.")
                raise typer.Exit(1)
        try:
            record = service.approve(
                job_id, session=session, profile=profile, artifacts_dir=Settings().artifacts_dir
            )
        except (service.ApplyError, BrowserBusyError) as exc:
            raise _fail(exc) from None
        if record.status == "submitted":
            typer.echo(f"[✓] Submitted. Confirmation screenshot: {record.screenshot}")
        else:
            _report(record)
            raise typer.Exit(1)


def _decision(job_id: str, action: str) -> None:
    with db_session() as session:
        try:
            if action == "skip":
                service.skip(job_id, session=session)
                typer.echo(f"[✓] Skipped {job_id}")
            else:
                service.mark_applied(job_id, session=session)
                typer.echo(f"[✓] Marked as applied: {job_id}")
        except service.ApplyError as exc:
            raise _fail(exc) from None


@apply_app.command()
def skip(job_id: str) -> None:
    """Do not apply to this job."""
    _decision(job_id, "skip")


@apply_app.command("mark-applied")
def mark_applied(job_id: str) -> None:
    """Record that you applied yourself (e.g. through a portal account)."""
    _decision(job_id, "mark-applied")
