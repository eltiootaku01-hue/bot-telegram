# -*- coding: utf-8 -*-
"""Deterministic MIG-3 evidence tests; no real browser or external service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import unittest
from unittest.mock import patch

from bot_ia.core.task_engine import (
    ResponseDisposition,
    TaskEngine,
    TaskState,
)
from bot_ia.core.task_scheduler import (
    TaskRoute,
    TaskScheduler,
)
from services.web_queue import (
    BotTicket,
    _QueueWorker,
    WebChatQueueManager,
    _WEB_MESA_UNICA,
)


class FakeExecutor:
    def __init__(self, *, fail_submit: bool = False) -> None:
        self.fail_submit = fail_submit
        self.submitted = []
        self.cancelled = []

    def submit(self, task) -> None:
        if self.fail_submit:
            raise RuntimeError("synthetic executor failure")
        self.submitted.append(task.task_id)

    def cancel(self, task_id: str) -> None:
        self.cancelled.append(task_id)

    def is_available(self) -> bool:
        return True


class FakeClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


class Mig3IdentityAndLifecycleTests(unittest.TestCase):
    def test_task_identity_rejects_wrong_and_terminal_responses(self) -> None:
        engine = TaskEngine()
        first = engine.create_task("gui", "webchat", task_id="task-a")
        engine.create_task("gui", "webchat", task_id="task-b")
        engine.start_task(first.task_id)

        self.assertIs(
            ResponseDisposition.DISCARDED,
            engine.validate_response("task-b"),
        )
        self.assertIs(
            ResponseDisposition.ACCEPTED,
            engine.validate_response("task-a"),
        )

        engine.complete("task-a")
        self.assertIs(
            ResponseDisposition.DISCARDED,
            engine.validate_response("task-a"),
        )

    def test_cancelled_task_rejects_late_response_and_cancel_is_idempotent(self) -> None:
        engine = TaskEngine()
        task = engine.create_task("gui", "webchat", task_id="cancel-me")
        engine.start_task(task.task_id)

        cancelled = engine.cancel(task.task_id)
        self.assertIs(TaskState.CANCELLED, cancelled.state)
        self.assertIs(TaskState.CANCELLED, engine.cancel(task.task_id).state)
        self.assertIs(
            ResponseDisposition.DISCARDED,
            engine.validate_response(task.task_id),
        )

    def test_scheduler_cancel_reaches_executor_and_does_not_reactivate_task(self) -> None:
        engine = TaskEngine()
        scheduler = TaskScheduler(engine)
        executor = FakeExecutor()
        scheduler.register_executor(TaskRoute.WEBCHAT, executor)
        task = engine.create_task("gui", "webchat", task_id="cancel-chain")
        scheduler.schedule(
            task.task_id,
            TaskRoute.WEBCHAT,
            resource_key=TaskScheduler.WEBCHAT_RESOURCE,
        )
        self.assertEqual(("cancel-chain",), scheduler.dispatch())

        cancelled = scheduler.cancel(task.task_id)
        self.assertIs(TaskState.CANCELLED, cancelled.state)
        self.assertEqual(["cancel-chain"], executor.cancelled)
        self.assertEqual(("cancel-chain",), scheduler.active_task_ids())
        scheduler.execution_finished(task.task_id)
        self.assertEqual((), scheduler.active_task_ids())
        self.assertIs(
            ResponseDisposition.DISCARDED,
            scheduler.accept_response(task.task_id),
        )

        cancelled_again = scheduler.cancel(task.task_id)
        self.assertIs(TaskState.CANCELLED, cancelled_again.state)
        self.assertEqual(["cancel-chain"], executor.cancelled)


class Mig3TimeoutFailureAndResourceTests(unittest.TestCase):
    def test_deadline_is_engine_owned_and_late_response_is_discarded(self) -> None:
        clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
        engine = TaskEngine(now_provider=clock.now)
        scheduler = TaskScheduler(engine)
        executor = FakeExecutor()
        scheduler.register_executor(TaskRoute.WEBCHAT, executor)

        task = engine.create_task(
            "gui",
            "webchat",
            task_id="deadline-task",
            deadline=clock.now() + timedelta(seconds=5),
        )
        scheduler.schedule(
            task.task_id,
            TaskRoute.WEBCHAT,
            resource_key=TaskScheduler.WEBCHAT_RESOURCE,
        )
        clock.advance(6)

        self.assertEqual((), scheduler.dispatch())
        self.assertIs(
            TaskState.TIMED_OUT,
            engine.snapshot(task.task_id).state,
        )
        self.assertEqual([], executor.submitted)
        self.assertIs(
            ResponseDisposition.DISCARDED,
            scheduler.accept_response(task.task_id),
        )

    def test_executor_failure_propagates_once_to_terminal_failed_state(self) -> None:
        engine = TaskEngine()
        scheduler = TaskScheduler(engine)
        executor = FakeExecutor(fail_submit=True)
        scheduler.register_executor(TaskRoute.WEBCHAT, executor)

        task = engine.create_task("gui", "webchat", task_id="fail-on-submit")
        scheduler.schedule(task.task_id, TaskRoute.WEBCHAT)

        self.assertEqual((), scheduler.dispatch())
        self.assertIs(
            TaskState.FAILED,
            engine.snapshot(task.task_id).state,
        )
        self.assertEqual((), scheduler.active_task_ids())
        self.assertIs(
            ResponseDisposition.DISCARDED,
            scheduler.accept_response(task.task_id),
        )

        result = scheduler.fail_from_executor(task.task_id)
        self.assertIs(TaskState.FAILED, result.state)

    def test_same_resource_allows_one_active_task_and_releases_for_next(self) -> None:
        engine = TaskEngine()
        scheduler = TaskScheduler(engine)
        executor = FakeExecutor()
        scheduler.register_executor(TaskRoute.WEBCHAT, executor)

        first = engine.create_task("gui", "webchat", task_id="resource-a")
        second = engine.create_task("gui", "webchat", task_id="resource-b")
        resource = TaskScheduler.WEBCHAT_RESOURCE
        scheduler.schedule(first.task_id, TaskRoute.WEBCHAT, resource_key=resource)
        scheduler.schedule(second.task_id, TaskRoute.WEBCHAT, resource_key=resource)

        self.assertEqual(("resource-a",), scheduler.dispatch())
        self.assertEqual(
            TaskState.WAITING,
            engine.snapshot(second.task_id).state,
        )
        self.assertEqual(("resource-a",), scheduler.active_task_ids())

        scheduler.execution_finished(first.task_id)
        self.assertEqual(["resource-a", "resource-b"], executor.submitted)
        self.assertEqual(("resource-b",), scheduler.active_task_ids())
        self.assertEqual(["resource-b"], executor.submitted[-1:])

        scheduler.cancel(second.task_id)
        self.assertEqual(("resource-b",), scheduler.active_task_ids())
        scheduler.execution_finished(second.task_id)
        self.assertEqual((), scheduler.active_task_ids())


class Mig3WebQueueProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.worker = _QueueWorker(
            timeout_ms=45000,
            circuit_threshold=3,
            circuit_cooldown_ms=10000,
        )

    def tearDown(self) -> None:
        if self.worker._mesa_unica_acquired:
            _WEB_MESA_UNICA.release()
            self.worker._mesa_unica_acquired = False

    def test_ticket_response_correlation_rejects_wrong_ticket_and_accepts_exact_identity(self) -> None:
        class SignalProbe:
            def __init__(self) -> None:
                self.events = []

            def emit(self, *args) -> None:
                self.events.append(args)

        manager = type("FakeWebQueue", (), {})()
        manager.current_ticket = BotTicket(
            "ticket-a",
            "Cari",
            "chat",
            "@u",
            "/cafe",
            "hola",
        )
        manager._response_pattern = re.compile(
            r'respuesta\s+a\s*\(\s*(?P<bot>[^()\\n]+?)\s+'
            r'(?P<ticket>[A-Za-z0-9_.:-]+)\s*\)\s*[“"](?P<text>.*?)[”"]',
            re.IGNORECASE | re.DOTALL,
        )
        manager._terminated_pattern = re.compile(
            r'\(\s*(?P<bot>[^()\\n]+?)\s+'
            r'(?P<ticket>[A-Za-z0-9_.:-]+)\s*\)#terminado',
            re.IGNORECASE,
        )
        manager.ticket_processed = SignalProbe()
        manager.response_observed_requested = SignalProbe()
        manager.terminated_requested = SignalProbe()
        manager.MAX_RESPONSE_PARSE_CHARS = 20_000

        self.assertFalse(
            WebChatQueueManager._consume_response(
                manager,
                
                'respuesta a (Cari ticket-b) “vieja”'
            )
        )
        self.assertTrue(
            WebChatQueueManager._consume_response(
                manager,
                'respuesta a (Cari ticket-a) “correcta”',
            )
        )
        self.assertEqual(
            [("ticket-a", "correcta")],
            manager.ticket_processed.events,
        )

        manager.current_ticket = None
        self.assertFalse(
            WebChatQueueManager._consume_response(
                manager,
                'respuesta a (Cari ticket-a) “tardía”',
            )
        )

    def test_operation_id_is_monotonic_when_browser_operation_is_cancelled(self) -> None:
        class FakePage:
            def runJavaScript(self, _script: str) -> None:
                return None

        class FakeWebView:
            def page(self) -> FakePage:
                return FakePage()

        manager = type("FakeWebQueue", (), {})()
        manager._web_operation_id = 4
        manager.web_view = FakeWebView()

        WebChatQueueManager._cancel_web_operation(manager)
        self.assertEqual(5, manager._web_operation_id)
        WebChatQueueManager._cancel_web_operation(manager)
        self.assertEqual(6, manager._web_operation_id)

    def test_queue_worker_duplicate_ticket_id_is_rejected(self) -> None:
        events = []
        self.worker.queue_error.connect(
            lambda ticket_id, reason: events.append((ticket_id, reason))
        )
        ticket = BotTicket(
            "dup",
            "Cari",
            "chat",
            "@u",
            "/cafe",
            "hola",
        )

        self.worker.is_busy = True
        self.worker.enqueue(ticket)
        self.worker.enqueue(ticket)

        self.assertEqual(
            [("dup", "DUPLICATE_TICKET_ID")],
            events,
        )

    def test_queue_worker_circuit_recovery_restores_capacity_without_duplicate_dispatch(self) -> None:
        events = []
        self.worker.capacity_restored.connect(lambda: events.append("restored"))
        self.worker.circuit_open = True
        self.worker._half_open_circuit()

        self.assertEqual(["restored"], events)
        self.assertFalse(self.worker.circuit_open)
        self.assertEqual(0, self.worker.consecutive_failures)


class Mig3QuickActionEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_quick_action_callback_uses_mutable_selected_bot_identity(self) -> None:
        from gui.app import BOT_MAP, CommandCenterWindow

        class Signal:
            def __init__(self) -> None:
                self.events = []

            def emit(self, *args) -> None:
                self.events.append(args)

        class Signals:
            def __init__(self) -> None:
                self.message_received = Signal()

        class Orchestrator:
            def __init__(self) -> None:
                self.callback = None
                self.waitress_id = None

            async def enqueue_task(self, *, waitress_id, priority, payload, callback):
                self.waitress_id = waitress_id
                self.callback = callback
                return True

        fake = type("FakeWindow", (), {})()
        fake._async_orchestrator = Orchestrator()
        fake._selected_bot_id = "sunna"
        fake.bridge_signals = Signals()

        CommandCenterWindow._schedule_async_quick_action(fake, "trivia")
        await __import__("asyncio").sleep(0)

        self.assertEqual("sunna", fake._async_orchestrator.waitress_id)

        fake._selected_bot_id = "cari"
        await fake._async_orchestrator.callback("respuesta")

        self.assertEqual(
            [(BOT_MAP["cari"].bot_id, "respuesta")],
            fake.bridge_signals.message_received.events,
        )
        self.assertNotEqual(
            BOT_MAP["sunna"].bot_id,
            fake.bridge_signals.message_received.events[0][0],
        )


class Mig3ClockAndObservationTests(unittest.TestCase):
    def test_task_engine_clock_is_injectable_while_scope_lock_uses_module_clock(self) -> None:
        clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
        engine = TaskEngine(now_provider=clock.now)
        task = engine.create_task("gui", "webchat", task_id="clock-task")

        self.assertEqual(
            clock.now(),
            task.created_at,
        )

        # This documents the remaining separate wall-clock dependency without
        # changing ScopeLock or protected runtime code in MIG-3.
        from bot_ia.supervisor.scope import ScopeLock

        scope = ScopeLock.create(
            scope_id="scope-clock",
            task_id=task.task_id,
            repository_root=".",
            scope_owner="human",
            authorization="auth",
            expires_at="2999-01-01T00:00:00Z",
        )
        self.assertEqual("ACTIVE", scope.current_status().value)

    def test_scheduler_observation_exposes_pending_and_active_only(self) -> None:
        engine = TaskEngine()
        scheduler = TaskScheduler(engine)
        executor = FakeExecutor()
        scheduler.register_executor(
            TaskRoute.WEBCHAT,
            executor,
            default_resource_key=TaskScheduler.WEBCHAT_RESOURCE,
        )
        task = engine.create_task("gui", "webchat", task_id="observe-resource")
        scheduler.schedule(task.task_id, TaskRoute.WEBCHAT)

        from bot_ia.supervisor.boundary import TaskEngineBoundary
        from bot_ia.supervisor.runtime_observation import RuntimeObservation

        evidence = RuntimeObservation(
            TaskEngineBoundary(engine, scheduler)
        ).scheduler(scenario="mig3-resource")

        self.assertEqual(
            ("observe-resource",),
            evidence.metadata["snapshot"]["pending_task_ids"],
        )
        self.assertEqual((), evidence.metadata["snapshot"]["active_task_ids"])

        self.assertFalse(
            hasattr(evidence.metadata["snapshot"], "_resource_active")
        )


if __name__ == "__main__":
    unittest.main()
