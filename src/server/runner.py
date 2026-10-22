"""Background command runner with single-flight deduplication and queueing (see slice 8)."""

import asyncio
import dataclasses
import time
from collections.abc import Callable
from typing import Any

import httpx
from sqlalchemy.orm import Session, sessionmaker

from src.agents.llm import make_llm
from src.config.settings import Settings
from src.ingestion.firecrawl_client import FirecrawlClient
from src.profile.loader import ProfileLoader
from src.server.events import EventBus
from src.services import apply as apply_service
from src.services import scout as scout_service
from src.services import tailor as tailor_service
from src.services.common import CancelledError, CancelToken
from src.storage import repository as repo
from src.storage.models import CommandRun, CommandStatus


class CommandRunner:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        settings: Settings,
        bus: EventBus | None = None,
    ) -> None:
        self.sessions = sessions
        self.settings = settings
        self.bus = bus
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._cancel_tokens: dict[str, CancelToken] = {}
        self._worker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    def submit(
        self,
        command: str,
        params: dict[str, Any],
        requested_by: str = "human:user",
    ) -> tuple[CommandRun, bool]:
        with self.sessions() as session:
            active = repo.find_active_command_run(session, command)
            if active is not None:
                return active, False
            run = repo.save_command_run(
                session, command, params, requested_by=requested_by
            )
            session.commit()
            run_id = run.id
        self._cancel_tokens[run_id] = CancelToken()
        self._queue.put_nowait(run_id)
        with self.sessions() as session:
            fresh = repo.get_command_run(session, run_id)
            assert fresh is not None
            return fresh, True

    def cancel(self, run_id: str) -> bool:
        if run_id in self._cancel_tokens:
            self._cancel_tokens[run_id].cancel()
            return True
        with self.sessions() as session:
            run = repo.get_command_run(session, run_id)
            if run and run.status == CommandStatus.QUEUED:
                repo.finish_command_run(session, run_id, status=CommandStatus.CANCELLED)
                session.commit()
                return True
        return False

    async def _worker(self) -> None:
        while True:
            run_id = await self._queue.get()
            try:
                await self._execute(run_id)
            finally:
                self._cancel_tokens.pop(run_id, None)
                self._queue.task_done()

    async def _execute(self, run_id: str) -> None:
        with self.sessions() as session:
            run = repo.get_command_run(session, run_id)
            if run is None or run.status == CommandStatus.CANCELLED:
                return
            repo.start_command_run(session, run_id)
            repo.record_audit(
                session,
                actor=run.requested_by,
                action="COMMAND_STARTED",
                status="SUCCESS",
                target_id=run.id,
                details={"command": run.command, "params": run.params},
            )
            session.commit()
            command, params = run.command, dict(run.params)
            actor = run.requested_by

        token = self._cancel_tokens.get(run_id) or CancelToken()
        last_update = 0.0
        loop = asyncio.get_running_loop()

        def progress(stage: str, done: int, total: int, detail: str) -> None:
            nonlocal last_update
            now = time.monotonic()
            if now - last_update >= 0.25 or done == total or done == 0:
                last_update = now
                with self.sessions() as s:
                    repo.update_command_progress(
                        s,
                        run_id,
                        {"stage": stage, "done": done, "total": total, "detail": detail},
                    )
                    s.commit()
                if self.bus:
                    asyncio.run_coroutine_threadsafe(
                        self.bus.broadcast(
                            {
                                "type": "command_progress",
                                "run_id": run_id,
                                "stage": stage,
                                "done": done,
                                "total": total,
                                "detail": detail,
                            }
                        ),
                        loop,
                    )

        try:
            result = await asyncio.to_thread(
                self._run_sync, command, params, progress, token
            )
            with self.sessions() as session:
                repo.finish_command_run(
                    session, run_id, status=CommandStatus.SUCCEEDED, result=result
                )
                repo.record_audit(
                    session,
                    actor=actor,
                    action="COMMAND_FINISHED",
                    status="SUCCESS",
                    target_id=run_id,
                    details={"command": command, "result": result},
                )
                session.commit()
        except CancelledError:
            with self.sessions() as session:
                repo.finish_command_run(session, run_id, status=CommandStatus.CANCELLED)
                repo.record_audit(
                    session,
                    actor=actor,
                    action="COMMAND_FINISHED",
                    status="WARNING",
                    target_id=run_id,
                    details={"command": command, "status": "cancelled"},
                )
                session.commit()
        except Exception as exc:
            with self.sessions() as session:
                repo.finish_command_run(
                    session, run_id, status=CommandStatus.FAILED, error=str(exc)
                )
                repo.record_audit(
                    session,
                    actor=actor,
                    action="COMMAND_FINISHED",
                    status="FAILURE",
                    target_id=run_id,
                    details={"command": command, "error": str(exc)},
                )
                session.commit()

    def _run_sync(
        self,
        command: str,
        params: dict[str, Any],
        progress: Callable[[str, int, int, str], None],
        cancel: CancelToken,
    ) -> dict[str, Any]:
        profile = ProfileLoader(self.settings.profile_path).load()
        with self.sessions() as session:
            if command == "scout_sweep":
                with httpx.Client(headers={"User-Agent": "job-butler/0.1"}) as http:
                    firecrawl = None
                    if self.settings.firecrawl_api_key:
                        firecrawl = FirecrawlClient(
                            self.settings.firecrawl_api_key,
                            http,
                            self.settings.firecrawl_state_dir,
                            daily_credits=self.settings.max_daily_scrape_credits,
                        )
                    rep = scout_service.sweep(
                        profile,
                        session,
                        http,
                        firecrawl,
                        limit=params.get("limit", 20),
                        progress=progress,
                        cancel=cancel,
                    )
                    return dataclasses.asdict(rep)
            elif command == "scout_verify":
                with httpx.Client(headers={"User-Agent": "job-butler/0.1"}) as http:
                    pruned, counts = scout_service.verify(
                        session, http, profile, progress=progress, cancel=cancel
                    )
                    return {"pruned": pruned, "counts": counts}
            elif command == "tailor_one":
                llm = make_llm(self.settings)
                row, res = tailor_service.tailor_one(
                    params["job_id"],
                    profile=profile,
                    session=session,
                    llm=llm,
                    artifacts_dir=self.settings.artifacts_dir,
                )
                return {"job_id": row.id, "pages": res.pages, "resume": str(res.paths.resume)}
            elif command == "tailor_matches":
                llm = make_llm(self.settings)
                tailor_rep = tailor_service.tailor_matches(
                    profile=profile,
                    session=session,
                    llm=llm,
                    artifacts_dir=self.settings.artifacts_dir,
                    min_score=params.get("min_score", 75),
                    progress=progress,
                    cancel=cancel,
                )
                return {
                    "total": tailor_rep.total,
                    "succeeded": tailor_rep.succeeded,
                    "failed": tailor_rep.failed,
                }
            elif command == "prepare_application":
                rec = apply_service.prepare(
                    params["job_id"],
                    session=session,
                    profile=profile,
                    artifacts_dir=self.settings.artifacts_dir,
                    answers=params.get("answers"),
                )
                return {
                    "job_id": rec.job_id,
                    "status": rec.status,
                    "plan_fields": len(rec.plan),
                    "questions": len(rec.questions),
                }
            else:
                raise ValueError(f"Unknown command: {command}")
