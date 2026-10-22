"""Paginated, filterable audit log."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from src.server.deps import SessionDep
from src.storage import repository as repo

router = APIRouter(prefix="/api")


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    timestamp: datetime
    actor: str
    action: str
    target_id: str | None
    status: str
    duration_ms: int | None
    details: dict[str, Any]


class AuditPage(BaseModel):
    items: list[AuditOut]
    next_offset: int | None


@router.get("/audit", response_model=AuditPage)
def list_audit(
    session: SessionDep,
    actor: str | None = None,
    action: str | None = None,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditPage:
    rows = repo.query_audit(
        session, actor=actor, action=action, status=status, limit=limit + 1, offset=offset
    )  # One extra row tells us whether another page exists.
    items = [AuditOut.model_validate(r) for r in rows[:limit]]
    return AuditPage(items=items, next_offset=offset + limit if len(rows) > limit else None)
