# -*- coding: utf-8 -*-
"""Operational Sunna waitress binding tests."""

from datetime import datetime, timezone
import sqlite3
from pathlib import Path
import tempfile
import unittest

from bot_ia.core.task_engine import TaskState
from bot_ia.core.waitress_session_manager import WaitressSessionManager
from bot_ia.characters import SUNNA


class FakeSignal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)


class FakeWebQueue:
    def __init__(self) -> None:
        self.ticket_processed = FakeSignal()
        self.ticket_failed = FakeSignal()
        self.ticket_started = FakeSignal()
        self.ticket_finished = FakeSignal()
        self.enqueued = []

    def enqueue_bot_message(self, **kwargs) -> None:
        self.enqueued.append(kwargs)

    def cancel_ticket(self, _ticket_id: str) -> None:
        return None


class SunnaOperationalBindingTests(unittest.TestCase):
    @staticmethod
    def manager(directory: str, now: datetime, queue: FakeWebQueue) -> WaitressSessionManager:
        return WaitressSessionManager(
            Path(directory) / "work" / "bot_ia_memory.sqlite3",
            web_queue_manager=queue,
            timezone_name="America/Argentina/Buenos_Aires",
            now_provider=lambda: now,
        )

    def test_sunna_operational_registration_reaches_character_projection(self) -> None:
        now = datetime(2026, 9, 24, 21, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            queue = FakeWebQueue()
            manager = self.manager(directory, now, queue)

            connection = sqlite3.connect(
                Path(directory) / "work" / "bot_ia_memory.sqlite3"
            )
            try:
                row = connection.execute(
                    "SELECT waitress_id, display_name, role, shift_type, "
                    "shift_start_hour, shift_end_hour, is_busy, is_resting, "
                    "last_ticket_at, personality_prompt "
                    "FROM waitresses WHERE waitress_id='sunna'"
                ).fetchone()
            finally:
                connection.close()

            self.assertEqual(
                (
                    "sunna",
                    "Sunna",
                    "novice",
                    "NIGHT",
                    18,
                    2,
                    0,
                    0,
                    None,
                    "Anfitriona competitiva, directa y atenta durante el turno. "
                    "Mantiene su rol de mesera y orienta la interacción hacia la "
                    "mesa de 21 / Blackjack.",
                ),
                row,
            )

            session = manager.start_standard_session("1", "sunna")
            self.assertEqual("sunna", session.waitress_id)

            ticket_id = manager.queue_user_message("1", "hola Sunna")
            task = manager.task_engine.snapshot(ticket_id)

            self.assertIsNotNone(task)
            self.assertEqual(TaskState.RUNNING, task.state)
            self.assertEqual("sunna", task.context["waitress_id"])
            self.assertEqual("Sunna", task.context["bot_name"])
            self.assertTrue(queue.enqueued)
            self.assertEqual("sunna", queue.enqueued[0]["bot_name"])
            self.assertIn("Identidad canónica: Sunna.", queue.enqueued[0]["message"])
            self.assertIn("extremadamente silenciosa", queue.enqueued[0]["message"])
            self.assertIs(SUNNA, __import__("bot_ia.characters", fromlist=["SUNNA"]).SUNNA)
            self.assertNotIn(
                "Anfitriona competitiva, directa y atenta durante el turno.",
                queue.enqueued[0]["message"],
            )

            manager.shutdown()

    def test_existing_cari_remains_on_legacy_waitress_path(self) -> None:
        now = datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            queue = FakeWebQueue()
            manager = self.manager(directory, now, queue)

            session = manager.start_standard_session("2", "cari")
            self.assertEqual("cari", session.waitress_id)

            ticket_id = manager.queue_user_message("2", "hola Cari")
            task = manager.task_engine.snapshot(ticket_id)

            self.assertIsNotNone(task)
            self.assertEqual(TaskState.RUNNING, task.state)
            self.assertEqual("cari", task.context["waitress_id"])
            self.assertEqual("Cari", task.context["bot_name"])
            self.assertTrue(queue.enqueued)
            self.assertEqual("cari", queue.enqueued[0]["bot_name"])
            self.assertIn(
                "Profesional, atenta, servicial, amigable y algo novata.",
                queue.enqueued[0]["message"],
            )
            self.assertNotIn("Identidad canónica: Sunna.", queue.enqueued[0]["message"])

            manager.shutdown()


if __name__ == "__main__":
    unittest.main()
