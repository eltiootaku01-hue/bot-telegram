from __future__ import annotations

import sqlite3
import unittest

from bot_ia.memory.fts import MemoryFTS


class MemoryFTSTests(unittest.TestCase):
    def test_ensure_builds_rebuildable_index(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE memories (memory_id TEXT PRIMARY KEY, universe_id TEXT NOT NULL, user_id TEXT NOT NULL, conversation_id TEXT, content TEXT NOT NULL, tags TEXT NOT NULL)")
        connection.execute("INSERT INTO memories VALUES ('m1','one','u','c','Kuro remembers salmon','[\"fish\"]')")
        self.assertTrue(MemoryFTS.ensure(connection))
        self.assertEqual(("m1",), MemoryFTS.query(connection, universe_id="one", user_id="u", conversation_id="c", terms=("salmon",)))

    def test_update_trigger_keeps_index_in_sync(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE memories (memory_id TEXT PRIMARY KEY, universe_id TEXT NOT NULL, user_id TEXT NOT NULL, conversation_id TEXT, content TEXT NOT NULL, tags TEXT NOT NULL)")
        MemoryFTS.ensure(connection)
        connection.execute("INSERT INTO memories VALUES ('m1','one','u',NULL,'old text','[]')")
        connection.execute("UPDATE memories SET content='new text' WHERE memory_id='m1'")
        self.assertEqual(("m1",), MemoryFTS.query(connection, universe_id="one", user_id="u", conversation_id=None, terms=("new",)))
        self.assertEqual((), MemoryFTS.query(connection, universe_id="one", user_id="u", conversation_id=None, terms=("old",)))


if __name__ == "__main__":
    unittest.main()
