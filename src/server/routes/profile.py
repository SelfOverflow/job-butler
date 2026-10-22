"""Profile read/edit API. Every save is validated, backed up, and written atomically.

The editor works on the raw YAML (with ${VAR} placeholders), so secrets from
`.env` are never written into the profile file.
"""

from datetime import datetime
from typing import Any, Self

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError, model_validator

from src.config.settings import Settings
from src.profile.loader import ProfileError, ProfileLoader
from src.profile.updater import ProfileUpdater
from src.server.deps import SettingsDep

router = APIRouter(prefix="/api/profile")


class ProfileUpdate(BaseModel):
    yaml: str | None = None  # Full document from the YAML editor, saved verbatim.
    set: dict[str, str] | None = None  # dotted.path -> YAML value, from the form editor.

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.yaml is None) == (self.set is None):
            raise ValueError("Provide exactly one of `yaml` or `set`")
        return self


class RestoreRequest(BaseModel):
    name: str


def _updater(settings: Settings) -> ProfileUpdater:
    loader = ProfileLoader(settings.profile_path)
    return ProfileUpdater(loader, loader.path.parent / "backups")


def _errors(exc: ProfileError | ValidationError) -> list[dict[str, str]]:
    if isinstance(exc, ProfileError):
        return [{"loc": "", "msg": str(exc)}]
    return [{"loc": ".".join(str(p) for p in e["loc"]), "msg": e["msg"]} for e in exc.errors()]


@router.get("")
def get_profile(settings: SettingsDep) -> dict[str, Any]:
    loader = ProfileLoader(settings.profile_path)
    try:
        text = loader.path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(404, f"Profile not found: {loader.path}") from None
    try:
        profile: dict[str, Any] | None = loader.load().model_dump(mode="json")
        errors: list[dict[str, str]] = []
    except (ProfileError, ValidationError) as exc:
        profile, errors = None, _errors(exc)
    return {"yaml": text, "profile": profile, "errors": errors}


@router.put("")
def put_profile(update: ProfileUpdate, settings: SettingsDep) -> dict[str, Any]:
    updater = _updater(settings)
    try:
        if update.yaml is not None:
            profile = updater.replace_text(update.yaml)
        else:
            profile = updater.set_values(list((update.set or {}).items()))
    except (ProfileError, ValidationError) as exc:
        raise HTTPException(422, _errors(exc)) from None
    return {"profile": profile.model_dump(mode="json")}


@router.get("/backups")
def list_backups(settings: SettingsDep) -> list[dict[str, str]]:
    return [
        {"name": p.name, "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat()}
        for p in _updater(settings).list_backups()
    ]


@router.post("/restore")
def restore(request: RestoreRequest, settings: SettingsDep) -> dict[str, Any]:
    updater = _updater(settings)
    match = next((p for p in updater.list_backups() if p.name == request.name), None)
    if match is None:
        raise HTTPException(404, f"No such backup: {request.name}")
    try:
        profile = updater.restore(match)
    except (ProfileError, ValidationError) as exc:
        raise HTTPException(422, _errors(exc)) from None
    return {"profile": profile.model_dump(mode="json")}
