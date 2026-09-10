from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bot_ia.contracts import Confidence, UniverseDefinition, UniverseRegistry
from bot_ia.memory import MemoryStore, MemoryType


class MemoryRetrievalBoundsTests(unittest.TestCase):
    def test_relevant_memory_after_first_hundred_candidates_is_not_lost(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = UniverseRegistry()
            registry.register(UniverseDefinition("test_world", "Test World", root / "biblioteca"))
            store = MemoryStore(root, registry)

            for index in range(100):
                record = store.propose(
                    universe_id="test_world",
                    user_id="user",
                    conversation_id="conversation",
                    memory_type=MemoryType.NOTE,
                    content=f"Kuro recuerda pescado secundario {index}",
                    source=f"fixture-{index}",
                    provenance="test",
                    confidence=Confidence.LOW,
                )
                store.approve(record.memory_id, approved_by_author="test")

            target = store.propose(
                universe_id="test_world",
                user_id="user",
                conversation_id="conversation",
                memory_type=MemoryType.NOTE,
                content="Kuro recuerda una decisión irrepetible sobre el faro azul",
                source="fixture-target",
                provenance="test",
                confidence=Confidence.HIGH,
            )
            store.approve(target.memory_id, approved_by_author="test")

            matches = store.retrieve(
                universe_id="test_world",
                user_id="user",
                conversation_id="conversation",
                query="faro azul",
                limit=5,
            )

            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].record.memory_id, target.memory_id)

    def test_supersession_rolls_back_if_replacement_is_not_active(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = UniverseRegistry()
            registry.register(UniverseDefinition("test_world", "Test World", root / "biblioteca"))
            store = MemoryStore(root, registry)
            old = store.propose(
                universe_id="test_world", user_id="user", conversation_id=None,
                memory_type=MemoryType.NOTE, content="dato antiguo", source="old", provenance="test",
            )
            replacement = store.propose(
                universe_id="test_world", user_id="user", conversation_id=None,
                memory_type=MemoryType.NOTE, content="dato nuevo", source="new", provenance="test",
            )
            store.approve(old.memory_id, approved_by_author="test")

            with self.assertRaises(Exception):
                store.supersede(old.memory_id, replacement.memory_id)

            self.assertEqual(store.get(old.memory_id).status.value, "active")
            self.assertEqual(store.get(replacement.memory_id).status.value, "proposed")


if __name__ == "__main__":
    unittest.main()
