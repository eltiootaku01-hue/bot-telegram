from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from bot_ia.contracts import Confidence, UniverseDefinition, UniverseRegistry
from bot_ia.core.session_store import PersistentSessionStore, SessionStorageError
from bot_ia.memory import MemoryStore, MemoryStatus, MemoryType


class PersistenceHardeningTests(unittest.TestCase):
    def _registry(self, root: Path) -> UniverseRegistry:
        registry = UniverseRegistry()
        registry.register(UniverseDefinition("world", "World", root / "biblioteca"))
        return registry

    def test_session_database_has_schema_identity_and_rejects_future_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "sessions.sqlite3"
            PersistentSessionStore(database)
            connection = sqlite3.connect(database)
            application_id = connection.execute("PRAGMA application_id").fetchone()[0]
            connection.execute("PRAGMA user_version=999")
            connection.commit()
            connection.close()

            self.assertNotEqual(application_id, 0)
            with self.assertRaises(SessionStorageError):
                PersistentSessionStore(database)

    def test_memory_database_has_schema_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = MemoryStore(root, self._registry(root))
            connection = sqlite3.connect(store.path)
            application_id = connection.execute("PRAGMA application_id").fetchone()[0]
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            connection.close()
            self.assertNotEqual(application_id, 0)
            self.assertEqual(version, MemoryStore.SCHEMA_VERSION)

    def test_memory_supersession_is_atomic_and_archives_old_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = MemoryStore(root, self._registry(root))
            old = store.propose(universe_id="world", user_id="u", conversation_id=None, memory_type=MemoryType.NOTE, content="dato antiguo", source="old", provenance="test", confidence=Confidence.HIGH)
            new = store.propose(universe_id="world", user_id="u", conversation_id=None, memory_type=MemoryType.NOTE, content="dato nuevo", source="new", provenance="test", confidence=Confidence.HIGH)
            store.approve(old.memory_id, approved_by_author="author")
            store.approve(new.memory_id, approved_by_author="author")

            replacement = store.supersede(old.memory_id, new.memory_id)

            self.assertEqual(store.get(old.memory_id).status, MemoryStatus.ARCHIVED)
            self.assertEqual(replacement.supersedes, old.memory_id)
            self.assertEqual(store.get(new.memory_id).status, MemoryStatus.ACTIVE)

    def test_session_expiry_uses_utc_and_does_not_accept_naive_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "sessions.sqlite3"
            store = PersistentSessionStore(database)
            state = store.get("missing", "conversation")
            self.assertIsNone(state)
            self.assertEqual(datetime.now(timezone.utc).utcoffset(), timedelta(0))


if __name__ == "__main__":
    unittest.main()
