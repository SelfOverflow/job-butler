"""24/7 autopilot: run the pipeline stages on an interval, resiliently.

Each cycle hot-reloads the profile and hands every stage the same frozen
snapshot (a half-edited file falls back to the last valid profile). Stages run in
order and are isolated: one failing stage is recorded and the next still runs.
The wait between cycles is jittered and backs off exponentially after failing
cycles. Stages only ever *prepare* applications; nothing here submits.
"""

import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from src.profile.loader import ProfileError, ProfileLoader
from src.profile.models import CandidateProfile
from src.storage import repository as repo

ACTOR = "agent:autopilot"


@dataclass(frozen=True)
class Stage:
    name: str
    run: Callable[[CandidateProfile], str]  # Returns a one-line summary.


@dataclass
class CycleReport:
    results: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    ok: bool = True


class Autopilot:
    def __init__(
        self,
        loader: ProfileLoader,
        sessions: sessionmaker[Session],
        stages: Sequence[Stage],
        *,
        interval_minutes: float = 60,
        max_backoff_factor: int = 8,
        jitter: float = 0.1,
        sleep: Callable[[float], None] = time.sleep,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self.loader, self.sessions, self.stages = loader, sessions, list(stages)
        self.interval_s = interval_minutes * 60
        self.max_backoff_factor, self.jitter = max_backoff_factor, jitter
        self._sleep, self._rng = sleep, rng
        self.consecutive_failures = 0

    def _profile(self) -> tuple[CandidateProfile | None, list[str]]:
        try:
            self.loader.load()
        except (ProfileError, ValidationError) as exc:
            try:
                snapshot = self.loader.snapshot()
            except (ProfileError, ValidationError):
                return None, [f"No valid profile: {exc}"]
            return snapshot, [f"profile reload failed, using the last valid snapshot: {exc}"]
        return self.loader.snapshot(), []

    def run_cycle(self) -> CycleReport:
        started = time.monotonic()
        profile, warnings = self._profile()
        report = CycleReport(warnings=warnings, ok=profile is not None)
        if profile is not None:
            for stage in self.stages:
                try:
                    report.results[stage.name] = stage.run(profile)
                except Exception as exc:  # A 24/7 loop must survive any single stage.
                    report.results[stage.name] = f"failed: {exc}"
                    report.ok = False
        with self.sessions() as session:
            repo.record_audit(
                session,
                actor=ACTOR,
                action="AUTOPILOT_CYCLE",
                status="SUCCESS"
                if report.ok and not warnings
                else "WARNING"
                if profile
                else "FAILURE",
                duration_ms=round((time.monotonic() - started) * 1000),
                details={"stages": report.results, "warnings": warnings},
            )
            session.commit()
        return report

    def next_delay(self) -> float:
        """Interval x backoff (2^failures, capped) x jitter in [1 - j, 1 + j]."""
        backoff = min(1 << self.consecutive_failures, self.max_backoff_factor)
        return self.interval_s * backoff * (1 + self.jitter * (2 * self._rng() - 1))

    def run(
        self, max_cycles: int | None = None, on_cycle: Callable[[CycleReport], None] | None = None
    ) -> None:
        cycles = 0
        while max_cycles is None or cycles < max_cycles:
            report = self.run_cycle()
            cycles += 1
            self.consecutive_failures = 0 if report.ok else self.consecutive_failures + 1
            if on_cycle:
                on_cycle(report)
            if max_cycles is not None and cycles >= max_cycles:
                return
            self._sleep(self.next_delay())
