import unittest

from bot_ia.config import ProviderConfig, RuntimeConfig, ServiceConfig
from bot_ia.providers import build_provider_manager


class Phase14ProviderFactoryTests(unittest.TestCase):
    def runtime(self) -> RuntimeConfig:
        return RuntimeConfig(
            providers=(
                ProviderConfig(
                    "gemini",
                    "gemini-3.8-flash",
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
            ),
        )

    def test_enabled_gemini_is_constructed(self) -> None:
        manager = build_provider_manager(
            self.runtime(),
            key_loader=lambda _: "test-key",
        )

        self.assertIn("gemini", manager._providers)
        self.assertNotIn("openai", manager._providers)

    def test_disabled_provider_is_not_constructed(self) -> None:
        manager = build_provider_manager(
            self.runtime(),
            key_loader=lambda _: "test-key",
        )

        self.assertNotIn("openai", manager._providers)

    def test_multiple_enabled_providers_are_constructed(self) -> None:
        config = RuntimeConfig(
            providers=(
                ProviderConfig("gemini", "gemini-test"),
                ProviderConfig("openai", "openai-test"),
            ),
            services=(),
        )

        manager = build_provider_manager(
            config,
            key_loader=lambda _: "test-key",
        )

        self.assertIn("gemini", manager._providers)
        self.assertIn("openai", manager._providers)

    def test_unknown_enabled_provider_is_rejected(self) -> None:
        config = RuntimeConfig(
            providers=(
                ProviderConfig("unknown", "unknown-test"),
            ),
            services=(),
        )

        with self.assertRaises(ValueError):
            build_provider_manager(
                config,
                key_loader=lambda _: "test-key",
            )

    def test_transport_can_be_injected_per_provider(self) -> None:
        calls = []

        def fake_gemini_transport(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "ok"}]
                        }
                    }
                ]
            }

        config = RuntimeConfig(
            providers=(
                ProviderConfig("gemini", "gemini-test"),
            ),
            services=(),
        )

        manager = build_provider_manager(
            config,
            key_loader=lambda _: "test-key",
            transports={"gemini": fake_gemini_transport},
        )

        provider = manager._providers["gemini"]

        from bot_ia.providers import ProviderRequest

        response = provider.generate(
            ProviderRequest(
                "gemini",
                "gemini-test",
                "hola",
                16,
                1.0,
                "factory-test",
                "test",
            )
        )

        self.assertEqual("ok", response.output_text)
        self.assertEqual(1, len(calls))


if __name__ == "__main__":
    unittest.main()