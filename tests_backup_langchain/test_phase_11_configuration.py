import unittest

from bot_ia.config import ProviderConfig


class Phase11ConfigurationTests(unittest.TestCase):
    def test_provider_config_requires_provider_and_model(self) -> None:
        config = ProviderConfig("gemini", "gemini-test")

        self.assertEqual("gemini", config.provider_id)
        self.assertEqual("gemini-test", config.model)

    def test_provider_config_supports_fallback(self) -> None:
        config = ProviderConfig(
            "gemini",
            "gemini-test",
            fallback_provider="openai",
        )

        self.assertEqual("openai", config.fallback_provider)

    def test_provider_config_rejects_same_fallback(self) -> None:
        with self.assertRaises(ValueError):
            ProviderConfig(
                "gemini",
                "gemini-test",
                fallback_provider="gemini",
            )

    def test_provider_config_rejects_invalid_output_limit(self) -> None:
        with self.assertRaises(ValueError):
            ProviderConfig(
                "gemini",
                "gemini-test",
                max_output_tokens=0,
            )

    def test_provider_config_rejects_invalid_timeout(self) -> None:
        with self.assertRaises(ValueError):
            ProviderConfig(
                "gemini",
                "gemini-test",
                timeout_seconds=0,
            )

    def test_provider_config_can_be_used_by_workflow(self) -> None:
        from bot_ia.core.local_workflow import LocalWorkflow

        config = ProviderConfig(
            "gemini",
            "gemini-test",
            fallback_provider="openai",
            max_output_tokens=256,
            timeout_seconds=2.5,
        )

        workflow = LocalWorkflow(
            {},
            provider_config=config,
        )

        self.assertEqual("gemini", workflow._provider_config.provider_id)
        self.assertEqual("gemini-test", workflow._provider_config.model)
        self.assertEqual("openai", workflow._provider_config.fallback_provider)
        self.assertEqual(256, workflow._provider_config.max_output_tokens)
        self.assertEqual(2.5, workflow._provider_config.timeout_seconds)

    def test_legacy_provider_arguments_build_provider_config(self) -> None:
        from bot_ia.core.local_workflow import LocalWorkflow

        workflow = LocalWorkflow(
            {},
            provider_id="gemini",
            provider_model="gemini-test",
            fallback_provider="openai",
        )

        self.assertEqual("gemini", workflow._provider_config.provider_id)
        self.assertEqual("gemini-test", workflow._provider_config.model)
        self.assertEqual("openai", workflow._provider_config.fallback_provider)

    def test_runtime_file_loads_provider_config(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from bot_ia.config import load_provider_config

        with TemporaryDirectory() as temp:
            path = Path(temp) / "runtime.toml"
            path.write_text(
                """
[provider]
id = "gemini"
model = "gemini-test"
fallback = "openai"
max_output_tokens = 256
timeout_seconds = 2.5
""".strip(),
                encoding="utf-8",
            )

            config = load_provider_config(path)

        self.assertEqual("gemini", config.provider_id)
        self.assertEqual("gemini-test", config.model)
        self.assertEqual("openai", config.fallback_provider)
        self.assertEqual(256, config.max_output_tokens)
        self.assertEqual(2.5, config.timeout_seconds)

    def test_runtime_file_empty_fallback_becomes_none(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from bot_ia.config import load_provider_config

        with TemporaryDirectory() as temp:
            path = Path(temp) / "runtime.toml"
            path.write_text(
                """
[provider]
id = "local_fake"
model = "local-v1"
fallback = ""
""".strip(),
                encoding="utf-8",
            )

            config = load_provider_config(path)

        self.assertIsNone(config.fallback_provider)

    def test_default_provider_config_uses_project_config_path(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from bot_ia.config import load_default_provider_config

        with TemporaryDirectory() as temp:
            root = Path(temp)
            config_dir = root / "config"
            config_dir.mkdir()

            (config_dir / "runtime.toml").write_text(
                """
[provider]
id = "gemini"
model = "gemini-test"
fallback = "openai"
max_output_tokens = 512
timeout_seconds = 3.0
""".strip(),
                encoding="utf-8",
            )

            config = load_default_provider_config(root)

        self.assertEqual("gemini", config.provider_id)
        self.assertEqual("gemini-test", config.model)
        self.assertEqual("openai", config.fallback_provider)
        self.assertEqual(512, config.max_output_tokens)
        self.assertEqual(3.0, config.timeout_seconds)

if __name__ == "__main__":
    unittest.main()