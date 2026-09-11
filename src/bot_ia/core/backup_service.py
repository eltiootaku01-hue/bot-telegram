"""Coordinated backups for BOT-IA local SQLite state.

The databases remain the source of truth. Backups are validated derived artifacts
and never leave the local workspace through this service.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .sqlite_backup import SQLiteBackupManager


@dataclass(frozen=True, slots=True)
class BackupSnapshot:
    memory_path: Path
    sessions_path: Path


class BackupService:
    """Back up BOT-IA's memory and session stores with the same snapshot label."""

    MEMORY_APPLICATION_ID = 0x4249414D  # BIAM
    SESSION_APPLICATION_ID = 0x42494153  # BIAS
    SCHEMA_VERSION = 1

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self._memory = SQLiteBackupManager(self.MEMORY_APPLICATION_ID, self.SCHEMA_VERSION)
        self._sessions = SQLiteBackupManager(self.SESSION_APPLICATION_ID, self.SCHEMA_VERSION)

    def create_snapshot(self, destination_root: Path, *, label: str) -> BackupSnapshot:
        """Create and validate both SQLite backups under one local snapshot directory."""
        if not label or Path(label).name != label or label in {".", ".."}:
            raise ValueError("snapshot label must be a single safe path component")
        destination_root = destination_root.resolve()
        snapshot_root = destination_root / label
        snapshot_root.mkdir(parents=True, exist_ok=True)

        memory_source = self.workspace_root / "work" / "bot_ia_memory.sqlite3"
        sessions_source = self.workspace_root / "work" / "bot_ia_sessions.sqlite3"
        memory_target = snapshot_root / "bot_ia_memory.sqlite3"
        sessions_target = snapshot_root / "bot_ia_sessions.sqlite3"

        self._memory.create_backup(memory_source, memory_target)
        try:
            self._sessions.create_backup(sessions_source, sessions_target)
        except Exception:
            memory_target.unlink(missing_ok=True)
            raise
        return BackupSnapshot(memory_target, sessions_target)

    def inspect_snapshot(self, snapshot: BackupSnapshot) -> None:
        """Validate both stores before a snapshot is accepted for restoration."""
        self._memory.inspect(snapshot.memory_path)
        self._sessions.inspect(snapshot.sessions_path)
