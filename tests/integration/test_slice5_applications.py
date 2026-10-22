from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.ingestion.base import RawJobPosting
from src.ingestion.scorer import JobScore
from src.storage import repository as repo
from src.storage.database import init_db, make_engine, session_factory
from src.storage.models import PENDING_STATUSES, ApplicationStatus

QUESTIONS = [{"label": "Why us?", "kind": "textarea", "options": []}]


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = make_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    init_db(engine)
    with session_factory(engine)() as s:
        yield s
    engine.dispose()


def _job(session: Session, n: int) -> str:
    job = RawJobPosting(f"Engineer {n}", "Hooli", "Remote", f"https://x/{n}", "d", "greenhouse")
    row = repo.upsert_job(session, job, JobScore(90 - n, None, 0))
    session.commit()
    return row.id


def test_save_and_update_application(session: Session) -> None:
    job_id = _job(session, 1)
    plan = [{"label": "First Name", "value": "Jane", "source": "profile"}]
    record = repo.save_application(
        session, job_id, status=ApplicationStatus.NEEDS_INPUT, plan=plan, questions=QUESTIONS
    )
    session.commit()
    created = record.updated_at

    assert repo.get_application(session, job_id) is record
    assert (record.status, record.plan, record.questions, record.answers) == (
        "needs_input",
        plan,
        QUESTIONS,
        {},
    )

    repo.save_application(
        session, job_id, status=ApplicationStatus.AWAITING_REVIEW, answers={"Why us?": "Mission."}
    )
    session.commit()
    updated = repo.get_application(session, job_id)
    assert updated is not None
    assert (updated.status, updated.plan, updated.answers) == (
        "awaiting_review",
        plan,
        {"Why us?": "Mission."},
    )
    assert updated.updated_at >= created


def test_list_pending_applications_newest_first(session: Session) -> None:
    ids = [_job(session, n) for n in range(4)]
    statuses = [
        ApplicationStatus.BLOCKED,
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.AWAITING_REVIEW,
        ApplicationStatus.NEEDS_INPUT,
    ]
    for job_id, status in zip(ids, statuses, strict=True):
        repo.save_application(session, job_id, status=status)
        session.commit()

    pending = repo.list_applications(session, statuses=PENDING_STATUSES)
    assert [(a.job_id, a.status) for a in pending] == [
        (ids[3], "needs_input"),
        (ids[2], "awaiting_review"),
        (ids[0], "blocked"),
    ]
    assert pending[0].job.title == "Engineer 3"  # joined posting for display
    assert len(repo.list_applications(session)) == 4


def test_unknown_job_is_rejected(session: Session) -> None:
    with pytest.raises(KeyError):
        repo.save_application(session, "job_missing", status=ApplicationStatus.BLOCKED)
