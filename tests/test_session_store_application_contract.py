from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bot_ia.core.session_store import PersistentSessionStore


class SessionStoreApplicationContractTests(unittest.TestCase):
    def test_get_or_create_creates_and_reloads_persistent_state(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "sessions.sqlite3"
            store = PersistentSessionStore(path)
            created = store.get_or_create("user", "conversation", "one_neko_punch")
            self.assertIsNotNone(created)
            self.assertEqual(created.universe_id, "one_neko_punch")
            reloaded = store.get_or_create("user", "conversation", "one_neko_punch")
            self.assertEqual(reloaded.session_id, created.session_id)
            self.assertGreater(reloaded.expires_at, datetime.now(timezone.utc))


if __name__ == "__main__":
    unittest.main()
