# -*- coding: utf-8 -*-
import queue
import unittest

from PySide6.QtCore import QObject, Qt, Signal, Slot

from bot_ia.core.task_engine import TaskEngine, TaskState
from bot_ia.core.task_scheduler import ResponseDisposition, TaskScheduler
from services.web_queue import BotTicket, _QueueWorker, _WEB_MESA_UNICA
from PySide6.QtWidgets import QApplication


class _OrderingSignalSource(QObject):
    terminated_requested = Signal(str)
    ticket_processed = Signal(str, str)


class _QueuedTerminationReceiver(QObject):
    def __init__(self, engine: TaskEngine, order: list[str]) -> None:
        super().__init__()
        self.engine = engine
        self.order = order

    @Slot(str)
    def receive(self, task_id: str) -> None:
        snapshot = self.engine.snapshot(task_id)
        if snapshot is None or snapshot.state is not TaskState.COMPLETED:
            raise AssertionError(
                "terminated_received executed before TaskEngine.complete"
            )
        self.order.append("terminated_received")


class WebQueueCancellationTests(unittest.TestCase):
    def test_ticket_processed_completes_logically_before_queued_termination(self) -> None:
        app = QApplication.instance() or QApplication([])
        engine = TaskEngine()
        scheduler = TaskScheduler(engine)
        task = engine.create_task(
            "user",
            "webchat",
            task_id="signal-ordering",
        )
        task = engine.start_task(task.task_id)

        source = _OrderingSignalSource()
        order: list[str] = []
        receiver = _QueuedTerminationReceiver(engine, order)

        def on_ticket_processed(task_id: str, _response: str) -> None:
            disposition = scheduler.accept_response(task_id)
            self.assertEqual(
                ResponseDisposition.ACCEPTED,
                disposition,
            )
            order.append("logical_completed")

        source.ticket_processed.connect(on_ticket_processed)
        source.terminated_requested.connect(
            receiver.receive,
            Qt.ConnectionType.QueuedConnection,
        )

        source.terminated_requested.emit(task.task_id)
        source.ticket_processed.emit(
            task.task_id,
            'respuesta a (Cari signal-ordering) "ok"',
        )

        self.assertEqual(
            ["logical_completed"],
            order,
        )
        app.processEvents()
        self.assertEqual(
            ["logical_completed", "terminated_received"],
            order,
        )
        self.assertEqual(
            TaskState.COMPLETED,
            engine.snapshot(task.task_id).state,
        )


    def test_active_ticket_cancellation_releases_mesa_without_circuit_failure(self) -> None:
        worker = _QueueWorker(
            timeout_ms=45000,
            circuit_threshold=3,
            circuit_cooldown_ms=10000,
        )
        events = []
        worker.ticket_failed.connect(
            lambda ticket, reason: events.append(
                (ticket.ticket_id, ticket.status, reason)
            )
        )

        ticket = BotTicket(
            ticket_id="active",
            bot_name="Cari",
            action="chat",
            user="@u",
            channel="/cafe",
            message="hola",
        )
        self.assertTrue(_WEB_MESA_UNICA.acquire(blocking=False))
        worker.current_ticket = ticket
        worker.is_busy = True
        worker._mesa_unica_acquired = True

        try:
            worker.cancel_ticket("active")

            self.assertEqual("CANCELLED", ticket.status)
            self.assertIsNone(worker.current_ticket)
            self.assertFalse(worker.is_busy)
            self.assertEqual(0, worker.consecutive_failures)
            self.assertEqual(
                [("active", "CANCELLED", "TASK_CANCELLED")],
                events,
            )
            self.assertTrue(
                _WEB_MESA_UNICA.acquire(blocking=False)
            )
        finally:
            if worker._mesa_unica_acquired:
                _WEB_MESA_UNICA.release()
            try:
                _WEB_MESA_UNICA.release()
            except RuntimeError:
                pass

    def test_circuit_recovery_signals_scheduler_capacity(self) -> None:
        worker = _QueueWorker(
            timeout_ms=45000,
            circuit_threshold=3,
            circuit_cooldown_ms=10000,
        )
        events = []
        worker.capacity_restored.connect(lambda: events.append(True))
        worker.circuit_open = True

        worker._half_open_circuit()

        self.assertEqual([True], events)
        self.assertFalse(worker.circuit_open)
        self.assertEqual(0, worker.consecutive_failures)

    def test_queued_ticket_cancellation_keeps_remaining_fifo_order(self) -> None:
        worker = _QueueWorker(
            timeout_ms=45000,
            circuit_threshold=3,
            circuit_cooldown_ms=10000,
        )
        first = BotTicket("a", "Cari", "chat", "@u", "/cafe", "a")
        second = BotTicket("b", "Cami", "chat", "@u", "/cafe", "b")
        third = BotTicket("c", "Sunna", "chat", "@u", "/cafe", "c")

        worker.msg_queue.put(first)
        worker.msg_queue.put(second)
        worker.msg_queue.put(third)
        worker._queued_ids.update({"a", "b", "c"})

        worker.cancel_ticket("b")

        remaining = []
        while True:
            try:
                remaining.append(worker.msg_queue.get_nowait().ticket_id)
            except queue.Empty:
                break

        self.assertEqual(["a", "c"], remaining)
        self.assertEqual("CANCELLED", second.status)
        self.assertNotIn("b", worker._queued_ids)


if __name__ == "__main__":
    unittest.main()
