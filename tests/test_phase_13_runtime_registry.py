import unittest

from bot_ia.config import (
    ProviderConfig,
    RuntimeConfig,
    RuntimeRegistry,
    ServiceConfig,
)


class Phase13RuntimeRegistryTests(unittest.TestCase):
    def runtime(self) -> RuntimeConfig:
        return RuntimeConfig(
            providers=(
                ProviderConfig(
                    "gemini",
                    "gemini-3.8-flash",
                    max_output_tokens=16,
                    timeout_seconds=30.0,
                    enabled=True,
                ),
                ProviderConfig(
                    "openai",
                    "openai-test",
                    enabled=False,
                ),
            ),
            services=(
                ServiceConfig("supabase", enabled=False),
                ServiceConfig("telegram", enabled=False),
            ),
        )

    def test_enabled_provider_is_available(self) -> None:
        registry = RuntimeRegistry(self.runtime())

        provider = registry.provider("gemini")

        self.assertEqual("gemini", provider.provider_id)
        self.assertEqual("gemini-3.8-flash", provider.model)

    def test_disabled_provider_is_rejected(self) -> None:
        registry = RuntimeRegistry(self.runtime())

        with self.assertRaises(ValueError):
            registry.provider("openai")

    def test_enabled_service_is_available(self) -> None:
        config = RuntimeConfig(
            providers=(
                ProviderConfig("gemini", "gemini-test"),
            ),
            services=(
                ServiceConfig(
                    "supabase",
                    enabled=True,
                    url="https://example.invalid",
                ),
            ),
        )

        registry = RuntimeRegistry(config)

        service = registry.service("supabase")

        self.assertEqual("supabase", service.service_id)
        self.assertEqual("https://example.invalid", service.url)

    def test_disabled_service_is_rejected(self) -> None:
        registry = RuntimeRegistry(self.runtime())

        with self.assertRaises(ValueError):
            registry.service("telegram")

    def test_original_runtime_config_remains_available(self) -> None:
        config = self.runtime()
        registry = RuntimeRegistry(config)

        self.assertIs(config, registry.config)


if __name__ == "__main__":
    unittest.main()