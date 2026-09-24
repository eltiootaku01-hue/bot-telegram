# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import time
from pathlib import Path
import unittest

from bot_ia.core.models import Intent, Route, RouteDecision
from bot_ia.core.project_manager import ProjectManager
from bot_ia.contracts import Confidence
from bot_ia.interfaces.telegram import TelegramOutbound
from bot_ia.interfaces.telegram_outbox import TelegramOutboxStore
from bot_ia.providers import ProviderManager, ProviderRequest, ProviderResponse, ProviderStatus, ProviderUsage


class FakeProvider:
    provider_id = "fake"

    def __init__(self, account_id: str, *, fail: bool = False) -> None:
        self.account_id = account_id
        self.enabled = True
        self.default_model = "fake-model"
        self.default_max_output_tokens = 32
        self.default_timeout_seconds = 7.0
        self.cooldown_seconds = 1.0
        self.fail = fail
        self.calls = 0
        self.last_request = None

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        self.last_request = request
        if self.fail:
            from bot_ia.providers.errors import ProviderRemoteError
            raise ProviderRemoteError("temporary failure")
        return ProviderResponse(
            provider=self.provider_id,
            model=request.model,
            status=ProviderStatus.SUCCESS,
            output_text="ok",
            usage=ProviderUsage(1, 1, 2),
            latency_ms=0,
            request_id=request.request_id,
            account_id=self.account_id,
        )


class HardeningTests(unittest.TestCase):
    def test_telegram_outbox_preserves_ack_and_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TelegramOutboxStore(Path(directory) / "outbox.sqlite3")
            outbound = TelegramOutbound("123", "hello", "tavern")
            first = store.create_pending(42, outbound)
            self.assertEqual(0, first.next_chunk)
            store.ack_chunk(42, 1)
            second = store.create_pending(42, TelegramOutbound("999", "must not overwrite"))
            self.assertEqual("123", second.chat_id)
            self.assertEqual(1, second.next_chunk)
            store.mark_delivered(42)
            self.assertEqual("DELIVERED", store.get(42).status)

    def test_project_registry_recovers_from_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = ProjectManager(root)
            manager.create_novel("Primero")
            manager.create_novel("Segundo")
            registry = manager.registry_path
            backup = registry.with_suffix(".json.bak")
            self.assertTrue(backup.is_file())
            registry.write_text("{broken", encoding="utf-8")
            recovered = ProjectManager(root)
            self.assertEqual(("primero",), tuple(item.project_id for item in recovered.all()))
            self.assertEqual("[", registry.read_text(encoding="utf-8")[:1])

    def test_provider_manager_stops_when_total_budget_is_exhausted(self) -> None:
        provider = FakeProvider("one")
        manager = ProviderManager((provider,))
        decision = RouteDecision(
            Route.LLM,
            "test",
            Confidence.HIGH,
            Intent.CREATIVE_WRITING,
            "alpha_world",
            requires_llm=True,
            agent_id="ia_chan",
        )
        request = ProviderRequest(
            provider="fake",
            model="fake-model",
            input_text="hello",
            max_output_tokens=16,
            timeout_seconds=7.0,
            request_id="budget-1",
            escalation_reason="test",
            total_budget_seconds=15.0,
            started_at=time.monotonic() - 14.95,
        )
        outcome = manager.execute(decision, request)
        self.assertEqual(ProviderStatus.ERROR, outcome.response.status)
        self.assertEqual(0, provider.calls)

    def test_provider_timeout_is_capped_by_remaining_budget(self) -> None:
        provider = FakeProvider("one")
        manager = ProviderManager((provider,))
        decision = RouteDecision(
            Route.LLM,
            "test",
            Confidence.HIGH,
            Intent.CREATIVE_WRITING,
            "alpha_world",
            requires_llm=True,
            agent_id="ia_chan",
        )
        request = ProviderRequest(
            provider="fake",
            model="fake-model",
            input_text="hello",
            max_output_tokens=16,
            timeout_seconds=30.0,
            request_id="budget-2",
            escalation_reason="test",
            total_budget_seconds=15.0,
        )
        outcome = manager.execute(decision, request)
        self.assertEqual(ProviderStatus.SUCCESS, outcome.response.status)
        self.assertIsNotNone(provider.last_request)
        self.assertLessEqual(provider.last_request.timeout_seconds, 15.0)


if __name__ == "__main__":
    unittest.main()
