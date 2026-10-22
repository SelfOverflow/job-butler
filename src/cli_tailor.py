"""`job-butler tailor`: tailored resume + cover letter per job, and PDF checks."""

from pathlib import Path
from typing import Annotated

import typer

from src.agents.llm import LLMError, make_llm
from src.agents.tailor.pdf_verifier import verify_pdf
from src.agents.tailor.runner import TailorError, TailorResult, tailor_job
from src.cli_common import db_session, friendly_errors, profile_loader, progress_bars, tier_labels
from src.config.settings import Settings
from src.storage import repository as repo
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
        if job_id:
            row = repo.get_job(session, job_id)
            if row is None:
                typer.echo(f"[✗] No job with id {job_id}")
                raise typer.Exit(1)
            rows = [row]
        else:
            rows = repo.list_active(session, min_score=min_score)
        labels, failures = tier_labels(), 0
        with progress_bars() as progress:
            progress("tailor", 0, len(rows), "")
            for done, row in enumerate(rows, start=1):
                try:
                    result = tailor_job(row, profile, llm, settings.artifacts_dir, session)
                except TailorError as exc:
                    failures += 1
                    typer.echo(f"[✗] {row.id} ({row.title} at {row.company}): {exc}")
                else:
                    typer.echo(f"\n{row.id}: {row.title} at {row.company}")
                    _report(row, result, labels.get(row.tier or "", row.tier or "no tier"))
                progress("tailor", done, len(rows), row.title)
    if all_matches:
        typer.echo(f"\nTailored {len(rows) - failures} of {len(rows)} job(s); {failures} failed")
    if failures:
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
    report = verify_pdf(path.read_bytes(), profile, keywords=[], max_pages=budget)
    for name, ok in report.checks.items():
        typer.echo(f"[{'✓' if ok else '✗'}] {name}")
    typer.echo(f"{report.pages} page(s), budget {budget}")
    for problem in report.problems:
        typer.echo(f"    {problem}")
    if not report.passed:
        raise typer.Exit(1)
