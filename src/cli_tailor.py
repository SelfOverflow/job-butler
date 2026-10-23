"""`job-butler tailor`: tailored resume + cover letter per job, and PDF checks."""

from pathlib import Path
from typing import Annotated

import typer

from src.agents.llm import LLMError, make_llm
from src.agents.tailor.runner import TailorError, TailorResult
from src.cli_common import db_session, friendly_errors, profile_loader, progress_bars, tier_labels
from src.config.settings import Settings
from src.services import tailor as tailor_service
from src.storage.models import JobPosting

tailor_app = typer.Typer(help="Tailor resumes and cover letters, or check a PDF.")


def _report(row: JobPosting, result: TailorResult, tier: str) -> None:
    budget = f"{result.pages}-page budget met"
    matched, report = len(result.report.keywords_matched), result.report
    total = matched + len(report.keywords_missing)
    for line in (
        f"Fit score: {row.score} ({tier})",
        f"Drafter: {result.selected} bullets selected across {result.roles} roles, "
        f"{result.kept} kept ({budget})",
        "Reviewer: every bullet verified verbatim against the profile",
        f"Text-layer check: {matched}/{total} keywords matched; "
        "LinkedIn, email and phone extractable",
        f"Resume: {result.paths.resume}",
        f"Cover letter: {result.paths.cover_pdf} and {result.paths.cover_txt}",
    ):
        typer.echo(f"[✓] {line}")


@tailor_app.callback(invoke_without_command=True)
def tailor(
    ctx: typer.Context,
    job_id: Annotated[str | None, typer.Option(help="Tailor one stored job.")] = None,
    all_matches: Annotated[bool, typer.Option(help="Tailor every active job.")] = False,
    min_score: Annotated[int, typer.Option(help="With --all-matches: minimum fit score.")] = 75,
) -> None:
    """Tailor a resume and cover letter for stored jobs."""
    if ctx.invoked_subcommand is not None:
        return
    if not job_id and not all_matches:
        typer.echo("[✗] Pass --job-id or --all-matches (see --help).")
        raise typer.Exit(1)
    settings = Settings()
    with friendly_errors():
        profile = profile_loader().load()
    try:
        llm = make_llm(settings)
    except LLMError as exc:
        typer.echo(f"[✗] {exc}")
        raise typer.Exit(1) from None

    with db_session() as session:
        labels = tier_labels()
        if job_id:
            try:
                with progress_bars() as progress:
                    row, result = tailor_service.tailor_one(
                        job_id,
                        profile=profile,
                        session=session,
                        llm=llm,
                        artifacts_dir=settings.artifacts_dir,
                        progress=progress,
                    )
            except TailorError as exc:
                typer.echo(f"[✗] {exc}")
                raise typer.Exit(1) from None
            typer.echo(f"\n{row.id}: {row.title} at {row.company}")
            _report(row, result, labels.get(row.tier or "", row.tier or "no tier"))
        else:
            with progress_bars() as progress:
                report = tailor_service.tailor_matches(
                    profile=profile,
                    session=session,
                    llm=llm,
                    artifacts_dir=settings.artifacts_dir,
                    min_score=min_score,
                    progress=progress,
                )
            for item in report.items:
                if item.error:
                    typer.echo(
                        f"[✗] {item.job.id} ({item.job.title} at {item.job.company}): {item.error}"
                    )
                elif item.result:
                    typer.echo(f"\n{item.job.id}: {item.job.title} at {item.job.company}")
                    _report(
                        item.job,
                        item.result,
                        labels.get(item.job.tier or "", item.job.tier or "no tier"),
                    )
            typer.echo(
                f"\nTailored {report.succeeded} of {report.total} job(s); {report.failed} failed"
            )
            if report.failed:
                raise typer.Exit(1)


@tailor_app.command("verify-pdf")
def verify_pdf_command(
    path: Path,
    pages: Annotated[int | None, typer.Option(help="Page budget (default: international).")] = None,
) -> None:
    """Run the ATS text-layer check on any PDF."""
    with friendly_errors():
        profile = profile_loader().load()
    if not path.is_file():
        typer.echo(f"[✗] {path} not found")
        raise typer.Exit(1)
    budget = pages or profile.preferences.cv_page_budget_rules.international
    report = tailor_service.check_pdf(path.read_bytes(), profile=profile, max_pages=budget)
    for name, ok in report.checks.items():
        typer.echo(f"[{'✓' if ok else '✗'}] {name}")
    typer.echo(f"{report.pages} page(s), budget {budget}")
    for problem in report.problems:
        typer.echo(f"    {problem}")
    if not report.passed:
        raise typer.Exit(1)
