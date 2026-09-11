"""Coordinated backups for BOT-IA local SQLite state.

The databases remain the source of truth. Backups are validated derived artifacts
and never leave the local workspace through this service.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bot_ia.core.session_store import PersistentSessionStore
from bot_ia.memory.store import MemoryStore

from .sqlite_backup import SQLiteBackupManager, SQLiteBackupError


@dataclass(frozen=True, slots=True)
class BackupSnapshot:
    memory_path: Path
    sessions_path: Path


class BackupService:
    """Back up BOT-IA's memory and session stores with the live schema contracts."""

    MAX_COHERENCE_ATTEMPTS = 3

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self._memory = SQLiteBackupManager(MemoryStore.APPLICATION_ID, MemoryStore.SCHEMA_VERSION)
        self._sessions = SQLiteBackupManager(PersistentSessionStore.APPLICATION_ID, PersistentSessionStore.SCHEMA_VERSION)

    def _require_workspace_path(self, path: Path) -> Path:
        """Reject backup destinations outside BOT-IA's local workspace."""
        resolved = path.resolve()
        if not resolved.is_relative_to(self.workspace_root):
            raise ValueError("backup destination must remain inside the BOT-IA workspace")
        return resolved

    def create_snapshot(self, destination_root: Path, *, label: str) -> BackupSnapshot:
        """Create a validated pair from a period with no detected source changes.

        SQLite's Online Backup API makes each database snapshot internally
        consistent. The data-version guard adds a cross-store coherence check:
        if either source changes while the pair is being created, both artifacts
        are discarded and the pair is retried instead of being presented as a
        coherent snapshot.
        """
        if not label or Path(label).name != label or label in {".", ".."}:
            raise ValueError("snapshot label must be a single safe path component")
        destination_root = self._require_workspace_path(destination_root)
        snapshot_root = destination_root / label
        if snapshot_root.exists():
            raise ValueError("snapshot destination already exists")
        snapshot_root.mkdir(parents=True, exist_ok=False)

        memory_source = self.workspace_root / "work" / "bot_ia_memory.sqlite3"
        sessions_source = self.workspace_root / "work" / "bot_ia_sessions.sqlite3"
        memory_target = snapshot_root / "bot_ia_memory.sqlite3"
        sessions_target = snapshot_root / "bot_ia_sessions.sqlite3"

        try:
            for _attempt in range(self.MAX_COHERENCE_ATTEMPTS):
                before_memory = self._memory.data_version(memory_source)
                before_sessions = self._sessions.data_version(sessions_source)
                memory_target.unlink(missing_ok=True)
                sessions_target.unlink(missing_ok=True)

                self._memory.create_backup(memory_source, memory_target)
                self._sessions.create_backup(sessions_source, sessions_target)

                after_memory = self._memory.data_version(memory_source)
                after_sessions = self._sessions.data_version(sessions_source)
                if before_memory == after_memory and before_sessions == after_sessions:
                    return BackupSnapshot(memory_target, sessions_target)

            raise SQLiteBackupError("source databases changed during coordinated snapshot")
        except Exception:
            memory_target.unlink(missing_ok=True)
            sessions_target.unlink(missing_ok=True)
            snapshot_root.rmdir()
            raise

    def inspect_snapshot(self, snapshot: BackupSnapshot) -> None:
        """Validate both stores before a snapshot is accepted for restoration."""
        self._memory.inspect(snapshot.memory_path)
        self._sessions.inspect(snapshot.sessions_path)
