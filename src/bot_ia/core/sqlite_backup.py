"""Validated local backups for BOT-IA SQLite stores.

Backups are derived artifacts. The original SQLite database remains the
source of truth; no network transfer is performed here.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from pathlib import Path
import os
import sqlite3
import tempfile
from collections.abc import Iterator


class SQLiteBackupError(RuntimeError):
    """Raised when a BOT-IA SQLite backup cannot be trusted."""


class SQLiteBackupManager:
    """Create and restore validated SQLite snapshots inside a workspace."""

    def __init__(self, application_id: int, schema_version: int) -> None:
        if not 0 < application_id <= 0x7FFFFFFF:
            raise ValueError("application_id must be a positive 32-bit integer")
        if schema_version < 1:
            raise ValueError("schema_version must be positive")
        self.application_id = application_id
        self.schema_version = schema_version

    def inspect(self, database_path: Path) -> tuple[int, int]:
        """Return (application_id, user_version) after a full integrity check."""
        if not database_path.is_file():
            raise SQLiteBackupError("SQLite database does not exist")
        try:
            with closing(sqlite3.connect(database_path, timeout=10.0)) as connection:
                application_id = connection.execute("PRAGMA application_id").fetchone()[0]
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                result = connection.execute("PRAGMA integrity_check").fetchone()[0]
        except sqlite3.DatabaseError as error:
            raise SQLiteBackupError("SQLite database could not be opened") from error
        if result != "ok":
            raise SQLiteBackupError(f"SQLite integrity check failed: {result}")
        if application_id != self.application_id:
            raise SQLiteBackupError("SQLite database belongs to another application")
        if version > self.schema_version:
            raise SQLiteBackupError("SQLite database is newer than this BOT-IA version")
        return application_id, version

    @staticmethod
    def _data_version(connection: sqlite3.Connection) -> int:
        return int(connection.execute("PRAGMA data_version").fetchone()[0])

    @contextmanager
    def observe_data_version(self, database_path: Path) -> Iterator[sqlite3.Connection]:
        """Keep one connection open so PRAGMA data_version can observe other commits.

        SQLite's data_version is meaningful across repeated reads on the same
        connection. Opening a fresh connection for both reads would reset the
        observer baseline and could miss writes made by another connection.
        """
        if not database_path.is_file():
            raise SQLiteBackupError("SQLite database does not exist")
        try:
            with closing(sqlite3.connect(database_path, timeout=10.0)) as connection:
                connection.execute("PRAGMA busy_timeout=10000")
                yield connection
        except sqlite3.DatabaseError as error:
            raise SQLiteBackupError("SQLite database version could not be observed") from error

    def data_version(self, database_path: Path) -> int:
        """Return a one-shot data-version observation for diagnostics/tests."""
        with self.observe_data_version(database_path) as connection:
            return self._data_version(connection)

    def create_backup(self, source_path: Path, backup_path: Path) -> Path:
        """Create an atomic, integrity-checked snapshot of a live SQLite DB."""
        if source_path.resolve() == backup_path.resolve():
            raise SQLiteBackupError("backup destination must differ from source")
        self.inspect(source_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{backup_path.name}.", suffix=".tmp", dir=backup_path.parent)
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            with closing(sqlite3.connect(source_path, timeout=10.0)) as source, closing(sqlite3.connect(temp_path, timeout=10.0)) as destination:
                source.backup(destination)
                destination.commit()
            self.inspect(temp_path)
            os.replace(temp_path, backup_path)
            return backup_path
        except (sqlite3.DatabaseError, OSError) as error:
            raise SQLiteBackupError("SQLite backup could not be created") from error
        finally:
            temp_path.unlink(missing_ok=True)

    def restore_backup(self, backup_path: Path, destination_path: Path) -> Path:
        """Validate a backup and atomically replace the destination database."""
        if backup_path.resolve() == destination_path.resolve():
            raise SQLiteBackupError("restore destination must differ from backup")
        self.inspect(backup_path)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{destination_path.name}.", suffix=".restore", dir=destination_path.parent)
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            with closing(sqlite3.connect(backup_path, timeout=10.0)) as source, closing(sqlite3.connect(temp_path, timeout=10.0)) as destination:
                source.backup(destination)
                destination.commit()
            self.inspect(temp_path)
            os.replace(temp_path, destination_path)
            return destination_path
        except (sqlite3.DatabaseError, OSError) as error:
            raise SQLiteBackupError("SQLite backup could not be restored") from error
        finally:
            temp_path.unlink(missing_ok=True)
