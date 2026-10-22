"""The autopilot's real pipeline stages: sweep -> tailor -> prepare (never submit)."""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session, sessionmaker

from src.agents.llm import LLMClient, LLMError, make_llm
from src.agents.navigator.browser import BrowserBusyError
from src.agents.tailor.runner import TailorError, artifact_paths, tailor_job
from src.config.settings import Settings
from src.ingestion.firecrawl_client import FirecrawlClient
from src.ingestion.pipeline import run_sweep
from src.profile.models import CandidateProfile
from src.scheduler.autopilot import Stage
from src.services.apply import ApplyError, prepare
from src.storage import repository as repo

USER_AGENT = "job-butler/0.1 (+https://github.com/SelfOverflow/job-butler)"


@dataclass(frozen=True)
class AutopilotLimits:
    sweep_limit: int = 20  # Jobs verified and saved per sweep.
    tailor_per_cycle: int = 3  # Bounds LLM cost.
    prepare_per_cycle: int = 3  # Bounds browser time.
    min_score: int = 75


def build_stages(
    settings: Settings,
    sessions: sessionmaker[Session],
    limits: AutopilotLimits,
    llm_factory: Callable[[Settings], LLMClient] = make_llm,
) -> list[Stage]:
    def sweep(profile: CandidateProfile) -> str:
        with httpx.Client(headers={"User-Agent": USER_AGENT}) as http, sessions() as session:
            firecrawl = None
            if settings.firecrawl_api_key:
                firecrawl = FirecrawlClient(
                    settings.firecrawl_api_key,
                    http,
                    settings.firecrawl_state_dir,
                    daily_credits=settings.max_daily_scrape_credits,
                )
            r = run_sweep(profile, session, http, firecrawl, limit=limits.sweep_limit)
        return (
            f"discovered {r.discovered}, rejected {r.rejected}, stale {r.stale}, "
            f"saved {r.saved} ({r.new} new), market {r.market_postings}"
        )

    def tailor(profile: CandidateProfile) -> str:
        try:
            llm = llm_factory(settings)
        except LLMError as exc:
            return f"skipped: {exc}"
        ok = failed = 0
        with sessions() as session:
            pending = [
                j
                for j in repo.list_active(session, min_score=limits.min_score)
                if not artifact_paths(settings.artifacts_dir, j.id).resume.is_file()
            ]
            for row in pending[: limits.tailor_per_cycle]:
                try:
                    tailor_job(row, profile, llm, settings.artifacts_dir, session)
                    ok += 1
                except TailorError:
                    failed += 1
        return f"tailored {ok}, failed {failed}"

    def prepare_applications(profile: CandidateProfile) -> str:
        outcomes: Counter[str] = Counter()
        with sessions() as session:
            ready = [
                j
                for j in repo.list_active(session, min_score=limits.min_score)
                if artifact_paths(settings.artifacts_dir, j.id).resume.is_file()
                and repo.get_application(session, j.id) is None
            ]
            for row in ready[: limits.prepare_per_cycle]:
                try:
                    record = prepare(
                        row.id,
                        session=session,
                        profile=profile,
                        artifacts_dir=settings.artifacts_dir,
                    )
                    outcomes[record.status.replace("_", " ")] += 1
                except (ApplyError, BrowserBusyError):
                    outcomes["refused"] += 1
        detail = ", ".join(f"{n} {status}" for status, n in sorted(outcomes.items()))
        return f"prepared {sum(outcomes.values())}" + (f": {detail}" if detail else "")

    return [Stage("sweep", sweep), Stage("tailor", tailor), Stage("prepare", prepare_applications)]
