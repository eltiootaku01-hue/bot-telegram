"""Change Manager local: observa y valida; no ejecuta rollback automático."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


class PathOutsideWorkspaceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ChangeCheckpoint:
    target: Path
    exists: bool
    content_hash: str | None
    size: int | None
    captured_at: datetime


@dataclass(frozen=True, slots=True)
class ChangeDetection:
    checkpoint: ChangeCheckpoint
    exists_now: bool
    content_hash_now: str | None
    changed: bool


@dataclass(frozen=True, slots=True)
class ChangeReport:
    target: Path
    changed: bool
    valid: bool
    note: str


class ChangeManager:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def resolve_target(self, relative_target: str | Path) -> Path:
        target = (self.workspace_root / relative_target).resolve()
        if not target.is_relative_to(self.workspace_root):
            raise PathOutsideWorkspaceError("target must remain inside workspace_root")
        return target

    @staticmethod
    def _hash(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def precheck(self, relative_target: str | Path) -> ChangeCheckpoint:
        target = self.resolve_target(relative_target)
        if target.exists() and not target.is_file():
            raise ValueError("ChangeManager only checkpoints files")
        exists = target.is_file()
        return ChangeCheckpoint(target, exists, self._hash(target) if exists else None, target.stat().st_size if exists else None, datetime.now(timezone.utc))

    def detect_change(self, checkpoint: ChangeCheckpoint) -> ChangeDetection:
        target = checkpoint.target
        exists_now = target.is_file()
        hash_now = self._hash(target) if exists_now else None
        return ChangeDetection(checkpoint, exists_now, hash_now, checkpoint.exists != exists_now or checkpoint.content_hash != hash_now)

    def validate(self, checkpoint: ChangeCheckpoint, *, must_exist: bool) -> ChangeReport:
        detection = self.detect_change(checkpoint)
        valid = detection.exists_now is must_exist
        return ChangeReport(checkpoint.target, detection.changed, valid, "validation passed" if valid else "required file existence does not match")
