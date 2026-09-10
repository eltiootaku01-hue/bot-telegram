from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from bot_ia.contracts import SessionState
from bot_ia.core.session_store import PersistentSessionStore


class PersistentSessionRuntimeTests(unittest.TestCase):
    def test_session_survives_store_recreation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "sessions.sqlite3"
            state = SessionState("telegram:user:conversation", "problemas_de_capibara", datetime.now(timezone.utc) + timedelta(hours=1), ("kuro",), ("chapter-1",), "chapter-1", "writing")
            PersistentSessionStore(database).put("user", "conversation", state)
            self.assertEqual(PersistentSessionStore(database).get("user", "conversation"), state)

    def test_expired_session_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "sessions.sqlite3"
            state = SessionState("telegram:user:conversation", "problemas_de_capibara", datetime.now(timezone.utc) - timedelta(seconds=1))
            store = PersistentSessionStore(database)
            store.put("user", "conversation", state)
            self.assertIsNone(store.get("user", "conversation"))

    def test_user_and_conversation_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "sessions.sqlite3"
            store = PersistentSessionStore(database)
            expires = datetime.now(timezone.utc) + timedelta(hours=1)
            store.put("user-a", "conversation", SessionState("a", "fragmentado", expires))
            store.put("user-b", "conversation", SessionState("b", "oasis_o_espejismo", expires))
            self.assertEqual(store.get("user-a", "conversation").universe_id, "fragmentado")
            self.assertEqual(store.get("user-b", "conversation").universe_id, "oasis_o_espejismo")


if __name__ == "__main__":
    unittest.main()
