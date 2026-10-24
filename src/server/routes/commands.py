"""Command Center API routes (see slice 8)."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from src.server.runner import CommandRunner
from src.storage import repository as repo

router = APIRouter(prefix="/api/commands", tags=["commands"])


class ScoutSweepParams(BaseModel):
    limit: int = Field(default=20, ge=1)


class ScoutVerifyParams(BaseModel):
    job_id: str | None = None
    delete_closed: bool = False


class TailorOneParams(BaseModel):
    job_id: str


class TailorMatchesParams(BaseModel):
    min_score: int = Field(default=75, ge=0, le=100)


class PrepareAppParams(BaseModel):
    job_id: str
    answers: dict[str, str] = Field(default_factory=dict)


COMMAND_SCHEMAS: dict[str, type[BaseModel]] = {
    "scout_sweep": ScoutSweepParams,
    "scout_verify": ScoutVerifyParams,
    "tailor_one": TailorOneParams,
    "tailor_matches": TailorMatchesParams,
    "prepare_application": PrepareAppParams,
}


class CommandRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    command: str
    params: dict[str, Any]
    status: str
    progress: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    requested_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@router.post("/{name}", status_code=status.HTTP_202_ACCEPTED)
async def launch_command(name: str, request: Request) -> dict[str, Any]:
    schema = COMMAND_SCHEMAS.get(name)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"Unknown command: {name}")

    try:
        raw = await request.json() if await request.body() else {}
        params = schema.model_validate(raw).model_dump()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    runner: CommandRunner = request.app.state.runner
    run, created = runner.submit(name, params, requested_by="human:user")
    return {"run_id": run.id, "status": run.status, "single_flight": not created}


@router.get("/runs", response_model=list[CommandRunOut])
def list_runs(request: Request) -> list[CommandRunOut]:
    sessions = request.app.state.sessions
    with sessions() as session:
        return [CommandRunOut.model_validate(r) for r in repo.list_command_runs(session)]


@router.get("/runs/{run_id}", response_model=CommandRunOut)
def get_run(run_id: str, request: Request) -> CommandRunOut:
    sessions = request.app.state.sessions
    with sessions() as session:
        run = repo.get_command_run(session, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"No run with id {run_id}")
        return CommandRunOut.model_validate(run)


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, request: Request) -> dict[str, str]:
    runner: CommandRunner = request.app.state.runner
    cancelled = runner.cancel(run_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Run not found or cannot be cancelled")
    return {"status": "cancelling"}
