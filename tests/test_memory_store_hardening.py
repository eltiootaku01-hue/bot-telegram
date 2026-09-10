import tempfile
import unittest
from pathlib import Path

from bot_ia.memory.models import MemoryStatus, MemoryType
from bot_ia.memory.store import MemoryStorageError, MemoryStore


class _Registry:
    def contains(self, universe_id: str) -> bool:
        return universe_id == "test_universe"


class MemoryStoreHardeningTests(unittest.TestCase):
    def _store(self) -> MemoryStore:
        self.tempdir = tempfile.TemporaryDirectory()
        return MemoryStore(Path(self.tempdir.name), _Registry())

    def tearDown(self) -> None:
        if hasattr(self, "store"):
            self.store.close()
        if hasattr(self, "tempdir"):
            self.tempdir.cleanup()

    def test_secret_in_metadata_is_rejected(self) -> None:
        self.store = self._store()
        with self.assertRaises(MemoryStorageError):
            self.store.propose(
                universe_id="test_universe",
                user_id="user",
                conversation_id="conversation",
                memory_type=MemoryType.NARRATIVE_CONTEXT,
                content="safe content",
                source="safe source",
                provenance="safe provenance",
                tags=("OPENAI_API_KEY=sk-123456789012",),
            )

    def test_update_requires_exactly_one_existing_row(self) -> None:
        self.store = self._store()
        record = self.store.propose(
            universe_id="test_universe",
            user_id="user",
            conversation_id="conversation",
            memory_type=MemoryType.NARRATIVE_CONTEXT,
            content="safe content",
            source="safe source",
            provenance="safe provenance",
        )
        with self.store._transaction() as connection:
            connection.execute("DELETE FROM memories WHERE memory_id=?", (record.memory_id,))

        with self.assertRaises(MemoryStorageError):
            self.store._update(record, status=MemoryStatus.ARCHIVED)


if __name__ == "__main__":
    unittest.main()
