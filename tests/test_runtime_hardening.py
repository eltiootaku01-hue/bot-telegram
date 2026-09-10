from pathlib import Path
import os
import tempfile
import unittest

from bot_ia.config import load_runtime_config
from bot_ia.contracts import UniverseDefinition, UniverseRegistry
from bot_ia.core.application import ApplicationRequest, BotApplication, InMemorySessionStore
from bot_ia.core.brain import LocalBrain
from bot_ia.core.local_workflow import LocalWorkflow
from bot_ia.core.router import Router
from bot_ia.memory import MemoryStore


class RuntimeHardeningTests(unittest.TestCase):
    def test_runtime_config_resolves_universe_from_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data_root = root / "knowledge"
            data_root.mkdir()
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "runtime.toml").write_text(
                """
[providers.ollama]
enabled = true
model = "test-model"

[universes.one_neko_punch]
display_name = "One Neko Punch"
root_path = "env:BOT_IA_TEST_UNIVERSE_ROOT"
language = "es"
""".strip(),
                encoding="utf-8",
            )

            previous = os.environ.get("BOT_IA_TEST_UNIVERSE_ROOT")
            os.environ["BOT_IA_TEST_UNIVERSE_ROOT"] = str(data_root)
            try:
                config = load_runtime_config(config_dir / "runtime.toml")
            finally:
                if previous is None:
                    os.environ.pop("BOT_IA_TEST_UNIVERSE_ROOT", None)
                else:
                    os.environ["BOT_IA_TEST_UNIVERSE_ROOT"] = previous

        self.assertEqual(data_root.resolve(), config.universe("one_neko_punch").root_path)

    def test_missing_universe_environment_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "runtime.toml").write_text(
                """
[providers.ollama]
enabled = true
model = "test-model"

[universes.one_neko_punch]
display_name = "One Neko Punch"
root_path = "env:BOT_IA_TEST_MISSING_ROOT"
language = "es"
""".strip(),
                encoding="utf-8",
            )
            os.environ.pop("BOT_IA_TEST_MISSING_ROOT", None)
            with self.assertRaisesRegex(ValueError, "BOT_IA_TEST_MISSING_ROOT"):
                load_runtime_config(config_dir / "runtime.toml")

    def test_first_turn_universe_change_creates_session(self) -> None:
        registry = UniverseRegistry()
        registry.register(UniverseDefinition("alpha_world", "Alpha World", Path("alpha")))
        app = BotApplication(LocalBrain(registry), Router(), InMemorySessionStore())

        response = app.handle(ApplicationRequest("u1", "c1", "cambiar a alpha_world"))

        self.assertEqual("alpha_world", response.brain.universe_id)
        self.assertEqual("updated", response.brain.state_status)
        self.assertIsNotNone(response.brain.state)
        self.assertEqual("alpha_world", response.brain.state.universe_id)

    def test_editorial_route_uses_editor_agent(self) -> None:
        registry = UniverseRegistry()
        registry.register(UniverseDefinition("alpha_world", "Alpha World", Path("alpha")))
        app = BotApplication(
            LocalBrain(registry),
            Router(),
            InMemorySessionStore(),
            default_universe_id="alpha_world",
            executor=LocalWorkflow({"alpha_world": ()}),
        )

        response = app.handle(ApplicationRequest("u1", "c1", "revisa la redacción de este párrafo"))

        self.assertEqual("agent", response.decision.route.value)
        self.assertEqual("editor", response.execution.agent_result.agent_id)

    def test_runtime_memory_store_is_wired_by_constructor_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = UniverseRegistry()
            registry.register(UniverseDefinition("alpha_world", "Alpha World", root / "alpha"))
            store = MemoryStore(root, registry)
            try:
                self.assertTrue(store.path.is_relative_to(root.resolve()))
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
