import sqlite3
import unittest

from bot_ia.memory.fts import MemoryFTS


class MemoryFTSBudgetTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute(
            "CREATE TABLE memories ("
            "memory_id TEXT PRIMARY KEY, universe_id TEXT NOT NULL, user_id TEXT NOT NULL, "
            "conversation_id TEXT, content TEXT NOT NULL, tags TEXT NOT NULL)"
        )
        for index in range(20):
            self.connection.execute(
                "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?)",
                (f"m-{index}", "novela-a", "user-a", None, f"gato escena {index}", "gato"),
            )
        self.connection.execute(
            "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?)",
            ("other-universe", "novela-b", "user-a", None, "gato escena externa", "gato"),
        )
        self.connection.execute(
            "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?)",
            ("other-user", "novela-a", "user-b", None, "gato escena otro usuario", "gato"),
        )
        self.connection.commit()
        self.assertTrue(MemoryFTS.ensure(self.connection))

    def tearDown(self):
        self.connection.close()

    def test_query_respects_candidate_budget(self):
        candidates = MemoryFTS.query(
            self.connection,
            universe_id="novela-a",
            user_id="user-a",
            conversation_id=None,
            terms=("gato",),
            budget=5,
        )
        self.assertEqual(len(candidates), 5)
        self.assertTrue(set(candidates).issubset({f"m-{index}" for index in range(20)}))

    def test_query_keeps_scope_filters_before_budget(self):
        candidates = MemoryFTS.query(
            self.connection,
            universe_id="novela-a",
            user_id="user-a",
            conversation_id=None,
            terms=("gato",),
            budget=50,
        )
        self.assertNotIn("other-universe", candidates)
        self.assertNotIn("other-user", candidates)
        self.assertEqual(len(candidates), 20)


if __name__ == "__main__":
    unittest.main()
