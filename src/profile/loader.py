"""Load `candidate_profile.yaml` (or JSON) into a validated `CandidateProfile`.

`${VAR}` and `${VAR:-default}` placeholders are resolved inside string values
after parsing, so environment values can never alter the document structure.
Process environment variables take precedence over the `.env` file.
"""

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values

from src.profile.models import CandidateProfile

_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


class ProfileError(Exception):
    """Profile could not be read or interpolated (schema errors raise ValidationError)."""


def interpolate(data: Any, env: Mapping[str, str]) -> Any:
    """Return `data` with placeholders in every nested string resolved from `env`."""
    missing: set[str] = set()

    def sub(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        value = env.get(name)
        if default is not None:
            return value or default  # Like bash: default applies when unset or empty.
        if value is None:
            missing.add(name)
            return match.group(0)
        return value

    def walk(node: Any) -> Any:
        if isinstance(node, str):
            return _PLACEHOLDER.sub(sub, node)
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    result = walk(data)
    if missing:
        raise ProfileError(f"Unset environment variable(s): {', '.join(sorted(missing))}")
    return result


class ProfileLoader:
    """Reads the profile from disk and keeps the last successfully validated copy."""

    def __init__(
        self,
        path: Path,
        env: Mapping[str, str] | None = None,
        env_file: Path | None = Path(".env"),
    ) -> None:
        self.path = path
        self._env = env
        self._env_file = env_file
        self._latest: CandidateProfile | None = None

    def _environment(self) -> Mapping[str, str]:
        if self._env is not None:
            return self._env
        file_values: dict[str, str] = {}
        if self._env_file is not None and self._env_file.is_file():
            file_values = {k: v for k, v in dotenv_values(self._env_file).items() if v is not None}
        return {**file_values, **os.environ}

    def read_raw(self) -> dict[str, Any]:
        """Parse and interpolate the file without schema validation."""
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ProfileError(f"Profile not found: {self.path}") from None
        try:
            data = yaml.safe_load(text)  # YAML is a superset of JSON.
        except yaml.YAMLError as exc:
            raise ProfileError(f"Invalid YAML in {self.path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ProfileError(f"Profile root must be a mapping: {self.path}")
        resolved: dict[str, Any] = interpolate(data, self._environment())
        return resolved

    def load(self) -> CandidateProfile:
        """Re-read the file; on success it becomes the source for `snapshot()`."""
        self._latest = CandidateProfile.model_validate(self.read_raw())
        return self._latest

    def snapshot(self) -> CandidateProfile:
        """Deep copy of the last valid profile, loading it on first use.

        A failed `load()` leaves the previous snapshot in place, so a half-edited
        file never interrupts a running sweep.
        """
        if self._latest is None:
            self.load()
        assert self._latest is not None
        return self._latest.model_copy(deep=True)
