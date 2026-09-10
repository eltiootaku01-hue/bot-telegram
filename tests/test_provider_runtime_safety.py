import unittest

from bot_ia.contracts import Confidence
from bot_ia.core.models import Intent, Route, RouteDecision
from bot_ia.providers import ProviderManager, ProviderRequest, ProviderStatus


class ExplodingProvider:
    provider_id = "exploding"
    account_id = "exploding"
    enabled = True
    default_model = "test-model"
    default_max_output_tokens = 32
    default_timeout_seconds = 1.0
    cooldown_seconds = 0.0

    def generate(self, request):
        raise RuntimeError("fixture failure")


class ProviderRuntimeSafetyTests(unittest.TestCase):
    def test_unexpected_adapter_exception_becomes_typed_error(self) -> None:
        manager = ProviderManager((ExplodingProvider(),))
        decision = RouteDecision(
            Route.LLM,
            "creative request",
            confidence=Confidence.HIGH,
            intent=Intent.CREATIVE_WRITING,
            universe_id="alpha_world",
            requires_llm=True,
            agent_id="ia_chan",
        )
        request = ProviderRequest(
            "exploding",
            "test-model",
            "hello",
            32,
            1.0,
            "req-1",
            "test",
        )

        outcome = manager.execute(decision, request)

        self.assertEqual(ProviderStatus.ERROR, outcome.response.status)
        self.assertEqual("ProviderRemoteError", outcome.response.error_type)
        self.assertEqual(("exploding",), outcome.attempts)


if __name__ == "__main__":
    unittest.main()
