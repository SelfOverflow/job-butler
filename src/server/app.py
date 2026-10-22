"""FastAPI application factory: REST API plus the compiled Next.js dashboard on one port."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.config.settings import Settings
from src.server import events
from src.server.auth import AuthMiddleware
from src.server.routes import analytics, audit, auth, commands, hitl, jobs, profile
from src.server.routes import settings as settings_route
from src.server.runner import CommandRunner
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory

FRONTEND_OUT = Path(__file__).resolve().parents[2] / "frontend" / "out"


def create_app(
    settings: Settings | None = None, frontend_dir: Path | None = FRONTEND_OUT
) -> FastAPI:
    settings = settings or Settings()
    if settings.auth_disabled and settings.host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("AUTH_DISABLED=true is only allowed on loopback (127.0.0.1)")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_url)
        init_db(engine)
        app.state.sessions = session_factory(engine)
        with app.state.sessions() as session:
            repo.fail_interrupted_runs(session)
            session.commit()
        app.state.bus = events.EventBus(app.state.sessions, settings.event_poll_seconds)
        await app.state.bus.start()
        poller = asyncio.create_task(app.state.bus.run())
        app.state.runner = CommandRunner(app.state.sessions, settings, app.state.bus)
        await app.state.runner.start()
        yield
        await app.state.runner.stop()
        poller.cancel()
        with suppress(asyncio.CancelledError):
            await poller
        engine.dispose()

    app = FastAPI(title="Job Butler", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(AuthMiddleware)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(settings_route.router)
    app.include_router(jobs.router)
    app.include_router(audit.router)
    app.include_router(profile.router)
    app.include_router(hitl.router)
    app.include_router(analytics.router)
    app.include_router(commands.router)
    app.include_router(events.router)
    if frontend_dir is not None and frontend_dir.is_dir():
        # Mounted last so API routes win; html=True serves <page>/index.html.
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    return app
