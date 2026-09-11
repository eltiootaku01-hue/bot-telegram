import sqlite3
import tempfile
import unittest
from pathlib import Path

from bot_ia.core.backup_service import BackupService
from bot_ia.core.sqlite_backup import SQLiteBackupError
from bot_ia.core.session_store import PersistentSessionStore
from bot_ia.memory.store import MemoryStore


class BackupServiceTests(unittest.TestCase):
    def _database(self, root: Path, name: str, application_id: int) -> Path:
        path = root / name
        connection = sqlite3.connect(path)
        try:
            connection.execute(f"PRAGMA application_id={application_id}")
            connection.execute("PRAGMA user_version=1")
            connection.execute("CREATE TABLE data(value TEXT NOT NULL)")
            connection.execute("INSERT INTO data(value) VALUES ('ok')")
            connection.commit()
        finally:
            connection.close()
        return path

    def test_snapshot_contains_both_stores(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            self._database(work, "bot_ia_memory.sqlite3", MemoryStore.APPLICATION_ID)
            self._database(work, "bot_ia_sessions.sqlite3", PersistentSessionStore.APPLICATION_ID)

            snapshot = BackupService(root).create_snapshot(root / "backups", label="snapshot-1")

            self.assertTrue(snapshot.memory_path.is_file())
            self.assertTrue(snapshot.sessions_path.is_file())
            BackupService(root).inspect_snapshot(snapshot)

    def test_snapshot_rolls_back_first_artifact_if_second_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            self._database(work, "bot_ia_memory.sqlite3", MemoryStore.APPLICATION_ID)
            self._database(work, "bot_ia_sessions.sqlite3", 1234)

            service = BackupService(root)
            with self.assertRaises(SQLiteBackupError):
                service.create_snapshot(root / "backups", label="snapshot-1")

            snapshot_root = root / "backups" / "snapshot-1"
            self.assertFalse((snapshot_root / "bot_ia_memory.sqlite3").exists())

    def test_rejects_path_traversal_label(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = BackupService(root)
            with self.assertRaises(ValueError):
                service.create_snapshot(root / "backups", label="../escape")


if __name__ == "__main__":
    unittest.main()
