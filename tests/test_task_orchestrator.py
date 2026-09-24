# -*- coding: utf-8 -*-
import asyncio
import unittest

from gui.task_orchestrator import (
    CircuitBreaker,
    Priority,
    QueueItem,
    TaskOrchestrator,
)


class SignalProbe:
    def __init__(self):
        self.events = []

    def emit_status_change(self, waitress_id, status):
        self.events.append((waitress_id, status))


class TaskOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_priority_queue_orders_high_before_low(self):
        async def worker(_waitress_id, payload):
            return payload["name"]

        orchestrator = TaskOrchestrator(worker)
        await orchestrator.enqueue_task(
            "cari",
            Priority.LOW,
            {"name": "low"},
        )
        await orchestrator.enqueue_task(
            "cari",
            Priority.HIGH,
            {"name": "high"},
        )
        await orchestrator.enqueue_task(
            "cari",
            Priority.MEDIUM,
            {"name": "medium"},
        )

        first = await orchestrator.queue.get()
        second = await orchestrator.queue.get()
        third = await orchestrator.queue.get()

        self.assertEqual(
            [Priority.HIGH.value, Priority.MEDIUM.value, Priority.LOW.value],
            [first.priority, second.priority, third.priority],
        )

        orchestrator.queue.task_done()
        orchestrator.queue.task_done()
        orchestrator.queue.task_done()

    async def test_worker_applies_12_second_timeout_and_fallback(self):
        async def worker(_waitress_id, _payload):
            await asyncio.sleep(1)

        orchestrator = TaskOrchestrator(worker)
        orchestrator.WEB_TIMEOUT_SECONDS = 0.01
        responses = []

        await orchestrator.enqueue_task(
            "sunna",
            Priority.HIGH,
            {"name": "timeout"},
            responses.append,
        )

        worker_task = asyncio.create_task(
            orchestrator.start_worker()
        )
        await orchestrator.drain()
        await orchestrator.stop_worker()
        await worker_task

        self.assertEqual(1, len(responses))
        self.assertIn("cartas", responses[0].lower())
        self.assertEqual(
            1,
            orchestrator.circuit_breaker.failure_counts["sunna"],
        )

    async def test_circuit_breaker_is_per_waitress_and_recovers(self):
        breaker = CircuitBreaker(
            max_failures=3,
            recovery_time_seconds=0,
        )

        for _ in range(3):
            breaker.record_failure("cari")

        self.assertFalse(breaker.is_open("cami"))
        self.assertFalse(breaker.is_open("cari"))
        self.assertEqual(2, breaker.failure_counts["cari"])

        breaker.record_success("cari")
        self.assertFalse(breaker.is_open("cari"))
        self.assertEqual(0, breaker.failure_counts["cari"])

    async def test_local_action_bypasses_web_worker(self):
        calls = []

        async def worker(_waitress_id, _payload):
            calls.append(True)
            return "web"

        orchestrator = TaskOrchestrator(worker)
        responses = []

        accepted = await orchestrator.enqueue_task(
            "chie",
            Priority.MEDIUM,
            {
                "is_local_action": True,
                "template_response": "acción local",
            },
            responses.append,
        )

        self.assertTrue(accepted)
        self.assertEqual(["acción local"], responses)
        self.assertEqual([], calls)

    async def test_async_callback_and_gui_signal_failure_do_not_break_queue(self):
        probe = SignalProbe()
        callback_results = []

        async def worker(_waitress_id, payload):
            return payload["answer"]

        async def callback(response):
            callback_results.append(response)

        orchestrator = TaskOrchestrator(
            worker,
            gui_signal_emitter=probe,
        )
        await orchestrator.enqueue_task(
            "chloe",
            Priority.HIGH,
            {"answer": "respuesta estable"},
            callback,
        )

        worker_task = asyncio.create_task(
            orchestrator.start_worker()
        )
        await orchestrator.drain()
        await orchestrator.stop_worker()
        await worker_task

        self.assertEqual(["respuesta estable"], callback_results)
        self.assertEqual(
            [
                ("chloe", "Procesando..."),
                ("chloe", "Online"),
            ],
            probe.events,
        )

    async def test_stop_worker_is_clean(self):
        async def worker(_waitress_id, _payload):
            return "ok"

        orchestrator = TaskOrchestrator(worker)
        worker_task = asyncio.create_task(
            orchestrator.start_worker()
        )

        await asyncio.sleep(0)
        self.assertTrue(orchestrator.is_running)

        await orchestrator.stop_worker()
        await worker_task

        self.assertFalse(orchestrator.is_running)


if __name__ == "__main__":
    unittest.main()
