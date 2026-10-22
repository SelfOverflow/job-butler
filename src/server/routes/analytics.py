"""Market trends and upskilling ROI from the latest sweep's snapshot."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from src.server.deps import SessionDep
from src.storage import repository as repo

router = APIRouter(prefix="/api/analytics")


class Trends(BaseModel):
    created_at: datetime | None
    total: int
    matched: int
    threshold: int
    demand: list[dict[str, Any]]


class UpskillOut(BaseModel):
    created_at: datetime | None
    matched: int
    threshold: int
    upskill: list[dict[str, Any]]


@router.get("/trends", response_model=Trends)
def trends(session: SessionDep) -> Trends:
    s = repo.latest_market_snapshot(session)
    if s is None:
        return Trends(created_at=None, total=0, matched=0, threshold=0, demand=[])
    return Trends(
        created_at=s.created_at,
        total=s.total,
        matched=s.matched,
        threshold=s.threshold,
        demand=s.demand,
    )


@router.get("/upskill", response_model=UpskillOut)
def upskill(session: SessionDep) -> UpskillOut:
    s = repo.latest_market_snapshot(session)
    if s is None:
        return UpskillOut(created_at=None, matched=0, threshold=0, upskill=[])
    return UpskillOut(
        created_at=s.created_at, matched=s.matched, threshold=s.threshold, upskill=s.upskill
    )
