"""Safe, validated mutations of `candidate_profile.yaml`.

Edits are applied to the raw round-trip YAML document, so `${VAR}` placeholders,
comments, and quoting survive. Every save validates the full result first, then
backs up the current file, then writes atomically (temp file + rename).
"""

import os
import shutil
import tempfile
from collections.abc import Callable, Sequence
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from src.profile.loader import ProfileError, ProfileLoader
from src.profile.models import AtomicBullet, CandidateProfile


def _round_trip_yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # Never re-wrap long bullet text.
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.representer.add_representer(
        type(None), lambda r, _: r.represent_scalar("tag:yaml.org,2002:null", "null")
    )
    return yaml


class ProfileUpdater:
    def __init__(
        self,
        loader: ProfileLoader,
        backups_dir: Path,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.loader = loader
        self.backups_dir = backups_dir
        self._clock = clock
        self._yaml = _round_trip_yaml()

    def _read_document(self) -> Any:
        try:
            return self._yaml.load(self.loader.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ProfileError(f"Profile not found: {self.loader.path}") from None
        except YAMLError as exc:
            raise ProfileError(f"Invalid YAML in {self.loader.path}: {exc}") from exc

    def _save(self, document: Any) -> CandidateProfile:
        self.loader.validate(document)  # Raises before anything touches disk.
        self._backup()
        buffer = StringIO()
        self._yaml.dump(document, buffer)
        self._atomic_write(buffer.getvalue())
        return self.loader.load()

    def _backup(self) -> Path:
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        base = f"{self.loader.path.stem}_{self._clock():%Y%m%d_%H%M%S}"
        target, n = self.backups_dir / f"{base}.yaml", 0
        while target.exists():
            n += 1
            target = self.backups_dir / f"{base}_{n}.yaml"
        shutil.copy2(self.loader.path, target)
        return target

    def _atomic_write(self, text: str) -> None:
        path = self.loader.path
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def set_value(self, dotted_path: str, raw_value: str) -> CandidateProfile:
        """Set e.g. `preferences.target_roles` to `raw_value` parsed as a YAML value."""
        return self.set_values([(dotted_path, raw_value)])

    def set_values(self, assignments: Sequence[tuple[str, str]]) -> CandidateProfile:
        """Apply several assignments, validated together and saved once (all or nothing)."""
        document = self._read_document()
        for dotted_path, raw_value in assignments:
            keys = dotted_path.split(".")
            if not all(keys):
                raise ProfileError(f"Invalid path: {dotted_path!r}")
            node = document
            for key in keys[:-1]:
                node = self._child(node, key, dotted_path)
            self._assign(node, keys[-1], self._yaml.load(raw_value), dotted_path)
        return self._save(document)

    @staticmethod
    def _child(node: Any, key: str, path: str) -> Any:
        try:
            return node[int(key)] if isinstance(node, list) else node[key]
        except (KeyError, IndexError, ValueError, TypeError):
            raise ProfileError(f"Path not found: {path!r} (at {key!r})") from None

    @staticmethod
    def _assign(node: Any, key: str, value: Any, path: str) -> None:
        try:
            if isinstance(node, list):
                node[int(key)] = value
            elif isinstance(node, dict):
                node[key] = value
            else:
                raise TypeError
        except (IndexError, ValueError, TypeError):
            raise ProfileError(f"Cannot set {path!r}: parent is not a container") from None

    def add_bullet(self, role_id: str, text: str, skills: Sequence[str]) -> AtomicBullet:
        """Append a verified bullet; its id is derived from its fact hash."""
        draft = AtomicBullet(id="pending", text=text, skills=tuple(skills))
        bullet_id = f"b_{draft.fact_hash[:8]}"
        document = self._read_document()
        role = next((r for r in document["work_experience"] if r.get("id") == role_id), None)
        if role is None:
            raise ProfileError(f"Unknown role id: {role_id!r}")
        role.setdefault("atomic_bullets", []).append(
            {"id": bullet_id, "text": draft.text, "skills": list(draft.skills)}
        )
        profile = self._save(document)
        return next(b for b in profile.bullets if b.id == bullet_id)

    def list_backups(self) -> list[Path]:
        if not self.backups_dir.is_dir():
            return []
        pattern = f"{self.loader.path.stem}_*.yaml"
        return sorted(self.backups_dir.glob(pattern), key=lambda p: p.stat().st_mtime_ns)

    def replace_text(self, text: str) -> CandidateProfile:
        """Replace the whole profile with `text`: validated, backed up, written verbatim."""
        try:
            document = self._yaml.load(text)
        except YAMLError as exc:
            raise ProfileError(f"Invalid YAML: {exc}") from exc
        if not isinstance(document, dict):
            raise ProfileError("Profile root must be a mapping")
        self.loader.validate(document)
        self._backup()
        self._atomic_write(text)
        return self.loader.load()

    def restore(self, backup: Path) -> CandidateProfile:
        """Replace the profile with `backup` (the current version is backed up first)."""
        return self.replace_text(backup.read_text(encoding="utf-8"))
