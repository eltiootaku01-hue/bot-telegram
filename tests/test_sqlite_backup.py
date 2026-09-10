import sqlite3
import tempfile
import unittest
from pathlib import Path

from bot_ia.core.sqlite_backup import SQLiteBackupError, SQLiteBackupManager


class SQLiteBackupTests(unittest.TestCase):
    APPLICATION_ID = 0x4249414D

    def _database(self, root: Path, name: str, value: str = "original") -> Path:
        path = root / name
        connection = sqlite3.connect(path)
        try:
            connection.execute(f"PRAGMA application_id={self.APPLICATION_ID}")
            connection.execute("PRAGMA user_version=1")
            connection.execute("CREATE TABLE data(value TEXT NOT NULL)")
            connection.execute("INSERT INTO data(value) VALUES (?)", (value,))
            connection.commit()
        finally:
            connection.close()
        return path

    def test_create_backup_is_valid_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._database(root, "source.sqlite3")
            backup = root / "backup.sqlite3"
            manager = SQLiteBackupManager(self.APPLICATION_ID, 1)

            manager.create_backup(source, backup)

            connection = sqlite3.connect(backup)
            try:
                self.assertEqual(connection.execute("SELECT value FROM data").fetchone()[0], "original")
            finally:
                connection.close()

    def test_restore_replaces_destination_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._database(root, "source.sqlite3", "saved")
            backup = root / "backup.sqlite3"
            destination = self._database(root, "destination.sqlite3", "old")
            manager = SQLiteBackupManager(self.APPLICATION_ID, 1)
            manager.create_backup(source, backup)

            manager.restore_backup(backup, destination)

            connection = sqlite3.connect(destination)
            try:
                self.assertEqual(connection.execute("SELECT value FROM data").fetchone()[0], "saved")
            finally:
                connection.close()

    def test_rejects_same_path_for_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._database(root, "source.sqlite3")
            manager = SQLiteBackupManager(self.APPLICATION_ID, 1)
            with self.assertRaises(SQLiteBackupError):
                manager.create_backup(source, source)

    def test_rejects_same_path_for_restore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = self._database(root, "backup.sqlite3")
            manager = SQLiteBackupManager(self.APPLICATION_ID, 1)
            with self.assertRaises(SQLiteBackupError):
                manager.restore_backup(backup, backup)

    def test_rejects_wrong_application_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._database(root, "foreign.sqlite3")
            connection = sqlite3.connect(path)
            try:
                connection.execute("PRAGMA application_id=1234")
                connection.commit()
            finally:
                connection.close()
            manager = SQLiteBackupManager(self.APPLICATION_ID, 1)
            with self.assertRaises(SQLiteBackupError):
                manager.inspect(path)

    def test_rejects_future_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._database(root, "future.sqlite3")
            connection = sqlite3.connect(path)
            try:
                connection.execute("PRAGMA user_version=99")
                connection.commit()
            finally:
                connection.close()
            manager = SQLiteBackupManager(self.APPLICATION_ID, 1)
            with self.assertRaises(SQLiteBackupError):
                manager.inspect(path)

    def test_rejects_corrupt_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = root / "broken.sqlite3"
            backup.write_bytes(b"not a sqlite database")
            manager = SQLiteBackupManager(self.APPLICATION_ID, 1)
            with self.assertRaises(SQLiteBackupError):
                manager.inspect(backup)


if __name__ == "__main__":
    unittest.main()
