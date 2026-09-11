from __future__ import annotations

import sqlite3
import unittest

from bot_ia.memory.fts import MemoryFTS


class MemoryFTSTests(unittest.TestCase):
    @staticmethod
    def _schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            "CREATE TABLE memories (memory_id TEXT PRIMARY KEY, universe_id TEXT NOT NULL, "
            "user_id TEXT NOT NULL, conversation_id TEXT, content TEXT NOT NULL, tags TEXT NOT NULL)"
        )

    def test_ensure_builds_rebuildable_index(self) -> None:
        connection = sqlite3.connect(":memory:")
        self._schema(connection)
        connection.execute("INSERT INTO memories VALUES ('m1','one','u','c','Kuro remembers salmon','[\"fish\"]')")
        self.assertTrue(MemoryFTS.ensure(connection))
        self.assertEqual(("m1",), MemoryFTS.query(connection, universe_id="one", user_id="u", conversation_id="c", terms=("salmon",)))

    def test_update_trigger_keeps_index_in_sync(self) -> None:
        connection = sqlite3.connect(":memory:")
        self._schema(connection)
        MemoryFTS.ensure(connection)
        connection.execute("INSERT INTO memories VALUES ('m1','one','u',NULL,'old text','[]')")
        connection.execute("UPDATE memories SET content='new text' WHERE memory_id='m1'")
        self.assertEqual(("m1",), MemoryFTS.query(connection, universe_id="one", user_id="u", conversation_id=None, terms=("new",)))
        self.assertEqual((), MemoryFTS.query(connection, universe_id="one", user_id="u", conversation_id=None, terms=("old",)))

    def test_ensure_rebuilds_when_projection_has_wrong_ids(self) -> None:
        connection = sqlite3.connect(":memory:")
        self._schema(connection)
        connection.execute("INSERT INTO memories VALUES ('m1','one','u',NULL,'source text','[]')")
        MemoryFTS.ensure(connection)
        connection.execute("DELETE FROM memories_fts")
        connection.execute("INSERT INTO memories_fts(memory_id, universe_id, user_id, conversation_id, content, tags) VALUES ('stale','one','u',NULL,'wrong','[]')")
        MemoryFTS.ensure(connection)
        self.assertEqual(("m1",), MemoryFTS.query(connection, universe_id="one", user_id="u", conversation_id=None, terms=("source",)))
        self.assertEqual((), MemoryFTS.query(connection, universe_id="one", user_id="u", conversation_id=None, terms=("wrong",)))

    def test_ensure_rebuilds_when_projection_has_same_id_but_wrong_content(self) -> None:
        connection = sqlite3.connect(":memory:")
        self._schema(connection)
        connection.execute("INSERT INTO memories VALUES ('m1','one','u',NULL,'authoritative text','[]')")
        MemoryFTS.ensure(connection)
        connection.execute("UPDATE memories_fts SET content='corrupted text' WHERE memory_id='m1'")
        MemoryFTS.ensure(connection)
        self.assertEqual(("m1",), MemoryFTS.query(connection, universe_id="one", user_id="u", conversation_id=None, terms=("authoritative",)))
        self.assertEqual((), MemoryFTS.query(connection, universe_id="one", user_id="u", conversation_id=None, terms=("corrupted",)))

    def test_query_uses_or_semantics_and_respects_scope(self) -> None:
        connection = sqlite3.connect(":memory:")
        self._schema(connection)
        connection.executemany(
            "INSERT INTO memories VALUES (?,?,?,?,?,?)",
            (
                ("m1", "one", "u", None, "Kuro eats salmon", "[]"),
                ("m2", "one", "u", None, "Kuro likes ramen", "[]"),
                ("m3", "two", "u", None, "Kuro eats salmon", "[]"),
            ),
        )
        MemoryFTS.ensure(connection)
        self.assertEqual(
            {"m1", "m2"},
            set(MemoryFTS.query(connection, universe_id="one", user_id="u", conversation_id=None, terms=("salmon", "ramen"))),
        )
        self.assertEqual(
            (),
            MemoryFTS.query(connection, universe_id="one", user_id="other", conversation_id=None, terms=("salmon",)),
        )


if __name__ == "__main__":
    unittest.main()
