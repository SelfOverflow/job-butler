"""SQLite engine shared by the CLI, web server, and background worker.

WAL mode plus a 30s busy timeout lets the scheduler write while the dashboard
reads without `database is locked` errors.
"""

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from src.storage.models import Base


def make_engine(url: str) -> Engine:
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return create_engine(url)
    if parsed.database and parsed.database != ":memory:":
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"timeout": 30.0, "check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    # Lightweight migration for databases created before `job_postings.status` existed.
    if "status" not in {c["name"] for c in inspect(engine).get_columns("job_postings")}:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE job_postings ADD COLUMN status VARCHAR(30) DEFAULT 'discovered'")
            )


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
