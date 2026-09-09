import unittest

from bot_ia.config import ProviderAccountConfig, ProviderConfig, RuntimeConfig, ServiceConfig
from bot_ia.core import Intent, Route, RouteDecision
from bot_ia.contracts import Confidence
from bot_ia.providers import (
    GroqProvider, OpenAIProvider, OpenRouterProvider, ProviderManager,
    ProviderRequest, ProviderStatus, build_provider_manager,
)
from bot_ia.providers.errors import ProviderTimeoutError


def decision():
    return RouteDecision(Route.LLM, "test", Confidence.HIGH, Intent.CREATIVE_WRITING, "one_neko_punch", requires_llm=True)


def request(provider="openai"):
    return ProviderRequest(provider, "primary-model", "hello", 20, 1.0, "r1", "test")


class ProviderEngineRepairTests(unittest.TestCase):
    def test_factory_builds_multiple_accounts_in_priority_order(self):
        config = RuntimeConfig(
            providers=(ProviderConfig(
                "openai", "gpt-primary", accounts=(
                    ProviderAccountConfig("second", "KEY2", priority=20),
                    ProviderAccountConfig("first", "KEY1", priority=10),
                )
            ),),
            services=(ServiceConfig("x"),),
        )
        manager = build_provider_manager(config, key_loader=lambda _: "key", transports={"openai": lambda *_: {"output_text": "ok"}})
        self.assertEqual(("openai:first", "openai:second"), tuple(manager._attempt_name(*pair) for pair in [("openai", "first"), ("openai", "second")]))

    def test_failed_primary_account_uses_second_account(self):
        calls = []
        def transport(*args):
            calls.append(args[0])
            if len(calls) == 1:
                raise ProviderTimeoutError("temporary")
            return {"output_text": "second", "usage": {"total_tokens": 2}}
        providers = (
            OpenAIProvider(account_id="first", api_key_env="KEY1", key_loader=lambda _: "key", transport=transport, cooldown_seconds=60),
            OpenAIProvider(account_id="second", api_key_env="KEY2", key_loader=lambda _: "key", transport=transport, cooldown_seconds=60),
        )
        outcome = ProviderManager(providers).execute(decision(), request())
        self.assertEqual(("openai:first", "openai:second"), outcome.attempts)
        self.assertEqual("second", outcome.response.output_text)
        self.assertTrue(outcome.response.fallback_used)

    def test_fallback_provider_uses_its_own_model_and_limits(self):
        seen = {}
        def transport(url, headers, payload, timeout):
            seen.update(url=url, payload=payload, timeout=timeout)
            if payload["model"] == "primary-model":
                raise ProviderTimeoutError("temporary")
            return {"output_text": "fallback"}
        primary = OpenAIProvider(key_loader=lambda _: "key", transport=transport)
        fallback = OpenRouterProvider(key_loader=lambda _: "key", transport=transport)
        configs = {
            "openai": ProviderConfig("openai", "primary-model", max_output_tokens=20, timeout_seconds=1),
            "openrouter": ProviderConfig("openrouter", "fallback-model", max_output_tokens=99, timeout_seconds=7),
        }
        outcome = ProviderManager((primary, fallback), provider_configs=configs).execute(decision(), request(), fallback_provider="openrouter")
        self.assertEqual("fallback-model", outcome.response.model)
        self.assertEqual(99, seen["payload"]["max_tokens"])
        self.assertEqual(7, seen["timeout"])
        self.assertEqual("https://openrouter.ai/api/v1/chat/completions", seen["url"])

    def test_groq_and_openrouter_use_chat_completions(self):
        for cls, base in ((GroqProvider, "https://api.groq.com/openai/v1"), (OpenRouterProvider, "https://openrouter.ai/api/v1")):
            seen = {}
            provider = cls(key_loader=lambda _: "key", transport=lambda url, h, p, t: seen.update(url=url, payload=p) or {"choices": [{"message": {"content": "ok"}}]})
            response = provider.generate(request(provider.provider_id))
            self.assertEqual("ok", response.output_text)
            self.assertEqual(base + "/chat/completions", seen["url"])
            self.assertEqual("user", seen["payload"]["messages"][0]["role"])

    def test_failed_account_is_in_cooldown_and_not_retried_immediately(self):
        calls = []
        provider = OpenAIProvider(key_loader=lambda _: "key", transport=lambda *_: calls.append(1) or (_ for _ in ()).throw(ProviderTimeoutError("temporary")), cooldown_seconds=60)
        manager = ProviderManager((provider,))
        first = manager.execute(decision(), request())
        second = manager.execute(decision(), request("openai"))
        self.assertEqual(ProviderStatus.ERROR, first.response.status)
        self.assertEqual(1, len(calls))
        self.assertEqual(ProviderStatus.ERROR, second.response.status)
        self.assertEqual((), second.attempts)


if __name__ == "__main__":
    unittest.main()
