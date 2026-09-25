# -*- coding: utf-8 -*-
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bot_ia.runtime import build_runtime
import bot_ia.__main__ as main_module


class Phase15RuntimeBootstrapTests(unittest.TestCase):
    def write_config(self, root: Path) -> None:
        config_dir = root / "config"
        config_dir.mkdir()
        (config_dir / "runtime.toml").write_text(
            """
[providers.openai]
enabled = true
model = "openai-test"
max_output_tokens = 16
timeout_seconds = 30.0
fallback = "groq"

[providers.groq]
enabled = true
model = "groq-test"
max_output_tokens = 16
timeout_seconds = 30.0
fallback = ""

[services.supabase]
enabled = false
url = ""

[services.telegram]
enabled = false
""".strip(),
            encoding="utf-8",
        )


    def test_telegram_entrypoint_injects_durable_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "memory.sqlite3"
            runtime = SimpleNamespace(memory_store=SimpleNamespace(path=db_path))

            class FakeClient:
                @classmethod
                def from_environment(cls):
                    return cls()

                def smoke_test(self):
                    return True

            captured = {}

            class FakePoller:
                def __init__(self, client, adapter, **kwargs):
                    captured["client"] = client
                    captured["adapter"] = adapter
                    captured.update(kwargs)

                def stop(self):
                    captured["stopped"] = True

                def run(self):
                    return SimpleNamespace(
                        polls=1,
                        updates_received=0,
                        updates_processed=0,
                        responses_sent=0,
                        transport_errors=0,
                    )

            with patch.object(main_module, "TelegramApiClient", FakeClient), \
                 patch.object(main_module, "TelegramPoller", FakePoller), \
                 patch.object(main_module, "TelegramProjectsAdapter", lambda application, runtime: object()):
                main_module._run_telegram(object(), runtime)

            self.assertIn("outbox_store", captured)
            self.assertIsNotNone(captured["outbox_store"])
            self.assertEqual(db_path, captured["outbox_store"]._path)

    def test_build_runtime_loads_project_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_config(root)
            runtime = build_runtime(root, key_loader=lambda _: "test-key")
        self.assertEqual("openai", runtime.registry.provider("openai").provider_id)
        self.assertEqual("openai-test", runtime.registry.provider("openai").model)

    def test_build_runtime_constructs_enabled_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_config(root)
            runtime = build_runtime(root, key_loader=lambda _: "test-key")
        self.assertIn("openai", runtime.provider_manager._providers)
        self.assertIn("groq", runtime.provider_manager._providers)

    def test_build_runtime_does_not_enable_disabled_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_config(root)
            runtime = build_runtime(root, key_loader=lambda _: "test-key")
        with self.assertRaises(ValueError):
            runtime.registry.service("telegram")

    def test_build_runtime_preserves_runtime_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_config(root)
            runtime = build_runtime(root, key_loader=lambda _: "test-key")
        self.assertEqual(("openai", "groq"), tuple(provider.provider_id for provider in runtime.config.providers))

    def test_runtime_bootstrap_is_offline(self) -> None:
        calls = []
        def transport(*args):
            calls.append(args)
            return {}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_config(root)
            build_runtime(root, key_loader=lambda _: "test-key", transports={"openai": transport, "groq": transport})
        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
