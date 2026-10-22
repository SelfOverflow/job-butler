"""FastAPI application factory: REST API plus the compiled Next.js dashboard on one port."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.config.settings import Settings
from src.server.routes import audit, jobs
from src.storage.database import init_db, make_engine, session_factory

FRONTEND_OUT = Path(__file__).resolve().parents[2] / "frontend" / "out"


def create_app(
    settings: Settings | None = None, frontend_dir: Path | None = FRONTEND_OUT
) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_url)
        init_db(engine)
        app.state.sessions = session_factory(engine)
        yield
        engine.dispose()

    app = FastAPI(title="Job Butler", lifespan=lifespan)
    app.state.settings = settings

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(jobs.router)
    app.include_router(audit.router)
    if frontend_dir is not None and frontend_dir.is_dir():
        # Mounted last so API routes win; html=True serves <page>/index.html.
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    return app
