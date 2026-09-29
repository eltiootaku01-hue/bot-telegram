# -*- coding: utf-8 -*-
"""Runtime-safe capability tests for FASE 2F-8F.

All provider/browser behavior is simulated. No real account, browser session,
credential, cookie or outbound message is used.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from bot_ia.core.web_queue import (
    NAVIGATION_TIMEOUT_MS,
    PAGE_TIMEOUT_MS,
    RESPONSE_TIMEOUT_MS,
    SOFT_RESET_AFTER_INTERACTIONS,
    WebQueueManager,
)
from services.web_queue import _QueueWorker, _WEB_MESA_UNICA
from gui.task_orchestrator import CircuitBreaker, TaskOrchestrator


class RuntimeSafeTimeoutAndBreakerTests(unittest.IsolatedAsyncioTestCase):
    async def test_orchestrator_timeout_is_independent_from_webqueue_timeout(self) -> None:
        async def slow_worker(_waitress_id: str, _payload: dict) -> str:
            await asyncio.sleep(0.02)
            return "late"

        orchestrator = TaskOrchestrator(slow_worker)
        orchestrator.WEB_TIMEOUT_SECONDS = 0.001
        received: list[str] = []

        async def callback(text: str) -> None:
            received.append(text)

        accepted = await orchestrator.enqueue_task(
            waitress_id="cari",
            priority=1,
            payload={"prompt": "synthetic timeout"},
            callback=callback,
        )
        self.assertTrue(accepted)

        await orchestrator._process_item(await orchestrator.queue.get())
        self.assertEqual(1, len(received))
        self.assertEqual("¡Uy! Se me cayó la bandeja... ¿Me repetís lo que necesitabas?", received[0])

    async def test_orchestrator_breaker_opens_after_three_failures_and_recovers(self) -> None:
        breaker = CircuitBreaker(max_failures=3, recovery_time_seconds=30.0)

        with patch("gui.task_orchestrator.time.monotonic", return_value=100.0):
            breaker.record_failure("sunna")
            breaker.record_failure("sunna")
            breaker.record_failure("sunna")

        with patch("gui.task_orchestrator.time.monotonic", return_value=129.9):
            self.assertTrue(breaker.is_open("sunna"))

        with patch("gui.task_orchestrator.time.monotonic", return_value=130.0):
            self.assertFalse(breaker.is_open("sunna"))

        self.assertEqual(2, breaker.failure_counts["sunna"])

    def test_timeout_layers_are_distinct_constants(self) -> None:
        self.assertEqual(10_000, RESPONSE_TIMEOUT_MS)
        self.assertEqual(15_000, PAGE_TIMEOUT_MS)
        self.assertEqual(20_000, NAVIGATION_TIMEOUT_MS)
        self.assertEqual(20, SOFT_RESET_AFTER_INTERACTIONS)
        self.assertNotEqual(RESPONSE_TIMEOUT_MS, PAGE_TIMEOUT_MS)
        self.assertNotEqual(PAGE_TIMEOUT_MS, NAVIGATION_TIMEOUT_MS)


class RuntimeSafeResourceAndProviderTests(unittest.TestCase):
    def tearDown(self) -> None:
        if _WEB_MESA_UNICA.locked():
            try:
                _WEB_MESA_UNICA.release()
            except RuntimeError:
                pass

    def test_webqueue_workers_share_one_process_resource_lock(self) -> None:
        first = _QueueWorker(
            timeout_ms=1,
            circuit_threshold=3,
            circuit_cooldown_ms=10_000,
        )
        second = _QueueWorker(
            timeout_ms=1,
            circuit_threshold=3,
            circuit_cooldown_ms=10_000,
        )

        events: list[tuple[str, str]] = []
        second.ticket_failed.connect(
            lambda ticket, reason: events.append((ticket.ticket_id, reason))
        )

        _WEB_MESA_UNICA.acquire()
        second.enqueue(
            __import__("services.web_queue", fromlist=["BotTicket"]).BotTicket(
                "mesa-b",
                "Cami",
                "chat",
                "@u",
                "/test",
                "synthetic",
            )
        )
        second._process_next()

        self.assertEqual([("mesa-b", "MESA_UNICA_TIMEOUT")], events)
        self.assertFalse(second.is_busy)

    async def _provider_contract(self) -> str:
        manager = WebQueueManager.__new__(WebQueueManager)
        manager._closing = False
        manager.pages = {"cari": object()}
        manager.interaction_counters = {}

        class FakeLocator:
            def __init__(self, text: str = "") -> None:
                self.text = text
                self.filled = ""

            async def fill(self, value: str) -> None:
                self.filled = value

            async def click(self) -> None:
                return None

            async def inner_text(self) -> str:
                return self.text

        response = FakeLocator("respuesta sintética")

        async def fake_locator(_page, selector_key: str, *, timeout_ms=RESPONSE_TIMEOUT_MS):
            if selector_key == "response_bubble":
                return response
            return FakeLocator()

        manager.get_active_locator = fake_locator
        return await manager.process_task(
            "cari",
            {"prompt": "provider simulation"},
        )

    def test_provider_behavior_is_tested_only_through_fake_page_contract(self) -> None:
        result = asyncio.run(self._provider_contract())
        self.assertEqual("respuesta sintética", result)


if __name__ == "__main__":
    unittest.main()
