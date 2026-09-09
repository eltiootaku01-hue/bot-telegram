from __future__ import annotations

import unittest

from bot_ia.contracts import Confidence
from bot_ia.core.models import Intent, Route, RouteDecision
from bot_ia.providers import (
    ProviderManager,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderUsage,
)


class FakeProvider:
    provider_id = "fake"

    def __init__(self, account_id: str) -> None:
        self.account_id = account_id
        self.enabled = True
        self.default_model = "fake-model"
        self.default_max_output_tokens = 32
        self.default_timeout_seconds = 5.0
        self.cooldown_seconds = 1.0
        self.calls = 0

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        return ProviderResponse(
            provider=self.provider_id,
            model=request.model,
            status=ProviderStatus.SUCCESS,
            output_text=f"account:{self.account_id}",
            usage=ProviderUsage(1, 1, 2),
            latency_ms=0,
            request_id=request.request_id,
            account_id=self.account_id,
        )


class ProviderManagerSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.account_a = FakeProvider("account-a")
        self.account_b = FakeProvider("account-b")
        self.manager = ProviderManager((self.account_a, self.account_b))
        self.decision = RouteDecision(
            Route.LLM,
            "creative request",
            Confidence.HIGH,
            Intent.CREATIVE_WRITING,
            "alpha_world",
            requires_llm=True,
            agent_id="ia_chan",
        )
        self.request = ProviderRequest(
            provider="fake",
            model="fake-model",
            input_text="hello",
            max_output_tokens=16,
            timeout_seconds=5.0,
            request_id="r1",
            escalation_reason="test",
            account_id="missing-account",
        )

    def test_unknown_explicit_account_does_not_silently_use_another_account(self) -> None:
        outcome = self.manager.execute(self.decision, self.request)

        self.assertEqual(ProviderStatus.ERROR, outcome.response.status)
        self.assertEqual(0, self.account_a.calls)
        self.assertEqual(0, self.account_b.calls)
        self.assertEqual(("fake:missing-account",), outcome.attempts)


if __name__ == "__main__":
    unittest.main()
