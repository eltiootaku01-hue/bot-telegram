# -*- coding: utf-8 -*-
import queue
import unittest

from services.web_queue import BotTicket, _QueueWorker, _WEB_MESA_UNICA


class WebQueueCancellationTests(unittest.TestCase):
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
