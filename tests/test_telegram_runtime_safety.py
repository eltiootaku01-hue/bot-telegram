# -*- coding: utf-8 -*-
import unittest
import sqlite3
import tempfile
import threading
from pathlib import Path

from bot_ia.interfaces.telegram_event_ledger import TelegramEventLedger
from bot_ia.interfaces.xp_audit import PassiveXPTracker, PassiveXPTrackerDrainError
from bot_ia.interfaces.telegram import TelegramAdapter, TelegramApiClient, TelegramOutbound, TelegramPoller, PollingConfig


class _ObservableEvent(threading.Event):
    def __init__(self) -> None:
        super().__init__()
        self.set_called = threading.Event()

    def set(self) -> None:
        super().set()
        self.set_called.set()


class TelegramRuntimeSafetyTests(unittest.TestCase):
    def test_adapter_close_stops_xp_writer_thread(self):
        adapter = TelegramAdapter(object())
        adapter._xp_tracker.record_message("shutdown-test", "telegram")
        thread = adapter._xp_tracker._thread
        self.addCleanup(adapter.close)
        self.assertIsNotNone(thread)
        self.assertTrue(thread.is_alive())

        adapter.close()

        self.assertFalse(
            thread.is_alive(),
            "TelegramAdapter.close() debe detener el escritor XP",
        )


    def test_xp_tracker_simple_drain_persists_all_accepted_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "xp.sqlite3"
            tracker = PassiveXPTracker(database, cooldown_seconds=0.0)

            accepted = [
                tracker.record_message(f"drain-user-{index}", "telegram")
                for index in range(3)
            ]

            self.assertEqual(3, sum(result.granted for result in accepted))
            tracker.stop()

            with sqlite3.connect(database) as db:
                persisted = db.execute(
                    "SELECT COUNT(*), COALESCE(SUM(xp), 0), COALESCE(SUM(messages), 0) "
                    "FROM xp_users"
                ).fetchone()

            self.assertEqual((3, 30, 3), persisted)
            self.assertEqual(0, tracker._queue.unfinished_tasks)
            self.assertEqual(0, tracker._queue.qsize())
            self.assertIsNotNone(tracker._thread)
            self.assertFalse(tracker._thread.is_alive())

    def test_xp_tracker_stop_waits_for_pending_queue_drain(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "xp.sqlite3"
            tracker = PassiveXPTracker(database, cooldown_seconds=0.0)
            tracker._stop = _ObservableEvent()

            original_get = tracker._queue.get
            get_started = threading.Event()
            release_get = threading.Event()

            def controlled_get(*, block=True, timeout=None):
                if not release_get.is_set():
                    get_started.set()
                    if not release_get.wait(5.0):
                        raise AssertionError("test did not release the queue consumer")
                return original_get(block=block, timeout=timeout)

            tracker._queue.get = controlled_get
            tracker._ensure_writer_started()
            self.assertTrue(get_started.wait(2.0))

            for index in range(4):
                result = tracker.record_message(f"pending-user-{index}", "telegram")
                self.assertTrue(result.granted)

            stop_finished = threading.Event()
            stopper = None

            try:
                def stop_tracker():
                    tracker.stop()
                    stop_finished.set()

                stopper = threading.Thread(target=stop_tracker, name="xp-pending-stop")
                stopper.start()

                self.assertTrue(tracker._stop.set_called.wait(2.0))
                self.assertTrue(stopper.is_alive())
                self.assertEqual(4, tracker._queue.unfinished_tasks)
                self.assertFalse(stop_finished.is_set())

                release_get.set()
                self.assertTrue(stop_finished.wait(5.0))

                with sqlite3.connect(database) as db:
                    persisted = db.execute(
                        "SELECT COUNT(*), COALESCE(SUM(xp), 0), COALESCE(SUM(messages), 0) "
                        "FROM xp_users"
                    ).fetchone()

                self.assertEqual((4, 40, 4), persisted)
                self.assertEqual(0, tracker._queue.unfinished_tasks)
                self.assertEqual(0, tracker._queue.qsize())
                self.assertFalse(stopper.is_alive())
                self.assertFalse(tracker._thread.is_alive())
            finally:
                release_get.set()
                if stopper is not None:
                    stopper.join(timeout=5.0)
                if tracker._thread is not None and tracker._thread.is_alive():
                    tracker.stop()

    def test_xp_tracker_stop_waits_for_in_flight_sqlite_item_and_remaining_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "xp.sqlite3"
            tracker = PassiveXPTracker(database, cooldown_seconds=0.0)
            tracker._stop = _ObservableEvent()
            insert_started = threading.Event()
            release_insert = threading.Event()
            insert_blocked = False
            original_connect = tracker._connect

            def blocked_connect():
                db = original_connect()

                def authorizer(action, table, _column, _database, _source):
                    nonlocal insert_blocked
                    if (
                        not insert_blocked
                        and action == sqlite3.SQLITE_INSERT
                        and table == "xp_users"
                    ):
                        insert_blocked = True
                        insert_started.set()
                        if not release_insert.wait(5.0):
                            raise AssertionError(
                                "test did not release the in-flight SQLite operation"
                            )
                    return sqlite3.SQLITE_OK

                db.set_authorizer(authorizer)
                return db

            tracker._connect = blocked_connect
            stopper = None

            try:
                first = tracker.record_message("in-flight-user", "telegram")
                self.assertTrue(first.granted)
                self.assertTrue(insert_started.wait(2.0))

                for index in range(3):
                    result = tracker.record_message(
                        f"in-flight-pending-{index}",
                        "telegram",
                    )
                    self.assertTrue(result.granted)

                stopper = threading.Thread(
                    target=tracker.stop,
                    name="xp-in-flight-stop",
                )
                stopper.start()

                self.assertTrue(tracker._stop.set_called.wait(2.0))
                self.assertTrue(stopper.is_alive())
                self.assertTrue(tracker._thread.is_alive())
                self.assertFalse(release_insert.is_set())

                release_insert.set()
                stopper.join(timeout=5.0)

                self.assertFalse(stopper.is_alive())
                self.assertFalse(tracker._thread.is_alive())
                self.assertEqual(0, tracker._queue.unfinished_tasks)
                self.assertEqual(0, tracker._queue.qsize())

                with sqlite3.connect(database) as db:
                    persisted = db.execute(
                        "SELECT COUNT(*), COALESCE(SUM(xp), 0), COALESCE(SUM(messages), 0) "
                        "FROM xp_users"
                    ).fetchone()

                self.assertEqual((4, 40, 4), persisted)
            finally:
                release_insert.set()
                if stopper is not None:
                    stopper.join(timeout=5.0)
                if tracker._thread is not None and tracker._thread.is_alive():
                    tracker.stop()

    def test_xp_tracker_producer_race_producer_wins_before_stop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "xp.sqlite3"
            tracker = PassiveXPTracker(database, cooldown_seconds=0.0)
            tracker._lock.acquire()
            produced = {}

            def produce():
                produced["result"] = tracker.record_message(
                    "producer-wins",
                    "telegram",
                )

            producer = threading.Thread(target=produce, name="xp-producer-wins")

            try:
                producer.start()
                self.assertTrue(producer.is_alive())

                tracker._lock.release()
                producer.join(timeout=5.0)

                self.assertFalse(producer.is_alive())
                self.assertTrue(produced["result"].granted)
                self.assertEqual(1, tracker._queue.unfinished_tasks)

                tracker.stop()

                with sqlite3.connect(database) as db:
                    persisted = db.execute(
                        "SELECT xp, messages FROM xp_users "
                        "WHERE user_id=? AND platform=?",
                        ("producer-wins", "telegram"),
                    ).fetchone()

                self.assertEqual((10, 1), persisted)
            finally:
                if tracker._lock.locked():
                    tracker._lock.release()
                producer.join(timeout=5.0)
                if tracker._thread is not None and tracker._thread.is_alive():
                    tracker.stop()

    def test_xp_tracker_producer_race_stop_wins_before_producer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "xp.sqlite3"
            tracker = PassiveXPTracker(database, cooldown_seconds=0.0)
            tracker._stop = _ObservableEvent()
            tracker._lock.acquire()

            stop_finished = threading.Event()

            def stop_tracker():
                tracker.stop()
                stop_finished.set()

            stopper = threading.Thread(target=stop_tracker, name="xp-stop-wins")

            try:
                stopper.start()
                self.assertTrue(stopper.is_alive())

                tracker._lock.release()
                self.assertTrue(tracker._stop.set_called.wait(2.0))
                self.assertTrue(stop_finished.wait(2.0))

                queue_before = tracker._queue.qsize()
                with self.assertRaisesRegex(
                    RuntimeError,
                    r"^PassiveXPTracker is stopped$",
                ):
                    tracker.record_message("producer-loses", "telegram")

                self.assertEqual(queue_before, tracker._queue.qsize())
                self.assertEqual(0, tracker._queue.unfinished_tasks)
            finally:
                if tracker._lock.locked():
                    tracker._lock.release()
                stopper.join(timeout=5.0)

    def test_xp_tracker_post_stop_rejects_without_queue_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "xp.sqlite3"
            tracker = PassiveXPTracker(database, cooldown_seconds=0.0)

            key = ("post-stop-user", "telegram")
            accepted = tracker.record_message(*key)
            self.assertTrue(accepted.granted)
            self.assertIn(key, tracker._last)

            tracker.stop()
            queue_before = tracker._queue.qsize()
            unfinished_before = tracker._queue.unfinished_tasks

            with self.assertRaisesRegex(
                RuntimeError,
                r"^PassiveXPTracker is stopped$",
            ):
                tracker.record_message(*key)

            self.assertEqual(queue_before, tracker._queue.qsize())
            self.assertEqual(unfinished_before, tracker._queue.unfinished_tasks)
            self.assertIn(key, tracker._last)

            tracker.stop()

    def test_xp_tracker_commit_failure_is_explicit_and_drain_continues(self):
        class FailingCommitConnection:
            def __init__(self, connection, state):
                self._connection = connection
                self._state = state

            def commit(self):
                if not self._state["failed"]:
                    self._state["failed"] = True
                    self._state["failure_event"].set()
                    raise sqlite3.OperationalError("forced commit failure")
                result = self._connection.commit()
                self._state["success_event"].set()
                return result

            def close(self):
                return self._connection.close()

            def __getattr__(self, name):
                return getattr(self._connection, name)

        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "xp.sqlite3"
            tracker = PassiveXPTracker(database, cooldown_seconds=0.0)
            state = {
                "failed": False,
                "failure_event": threading.Event(),
                "success_event": threading.Event(),
            }
            original_connect = tracker._connect

            def failing_connect():
                return FailingCommitConnection(original_connect(), state)

            tracker._connect = failing_connect

            self.assertTrue(
                tracker.record_message("commit-failure-user", "telegram").granted
            )
            self.assertTrue(
                tracker.record_message("commit-success-user", "telegram").granted
            )

            self.assertTrue(state["failure_event"].wait(2.0))
            self.assertTrue(state["success_event"].wait(2.0))

            with self.assertRaises(PassiveXPTrackerDrainError) as raised:
                tracker.stop()

            error = raised.exception
            self.assertEqual(1, error.failure_count)
            self.assertIsInstance(error.first_error, sqlite3.OperationalError)
            self.assertEqual(0, tracker._queue.unfinished_tasks)
            self.assertEqual(0, tracker._queue.qsize())
            self.assertFalse(tracker._thread.is_alive())

            with sqlite3.connect(database) as db:
                persisted = db.execute(
                    "SELECT COUNT(*), COALESCE(SUM(xp), 0), "
                    "COALESCE(SUM(messages), 0) FROM xp_users"
                ).fetchone()

            self.assertEqual((1, 10, 1), persisted)

            with self.assertRaises(PassiveXPTrackerDrainError):
                tracker.stop()

    def test_xp_tracker_multiple_items_leave_no_unfinished_work(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "xp.sqlite3"
            tracker = PassiveXPTracker(database, cooldown_seconds=0.0)
            accepted = 7

            for index in range(accepted):
                result = tracker.record_message(
                    "multi-item-user",
                    "telegram",
                )
                self.assertTrue(result.granted)

            tracker.stop()

            with sqlite3.connect(database) as db:
                persisted = db.execute(
                    "SELECT xp, messages FROM xp_users "
                    "WHERE user_id=? AND platform=?",
                    ("multi-item-user", "telegram"),
                ).fetchone()

            self.assertEqual((accepted * 10, accepted), persisted)
            self.assertEqual(0, tracker._queue.unfinished_tasks)
            self.assertTrue(tracker._queue.empty())
            self.assertFalse(tracker._thread.is_alive())


    def test_poller_stop_closes_adapter(self):
        class Adapter:
            def __init__(self):
                self.closed = False

            def handle_update(self, _update):
                return None

            def close(self):
                self.closed = True

        class Client:
            token = "test_token"

            def get_updates(self, *, offset=None, timeout_seconds=25):
                return ()

        adapter = Adapter()
        poller = TelegramPoller(
            Client(),
            adapter,
            event_ledger=self.event_ledger,
            sleeper=lambda _: None,
        )

        poller.stop()

        self.assertTrue(adapter.closed)

    def setUp(self) -> None:
        self._ledger_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._ledger_tmp.cleanup)
        self.event_ledger = TelegramEventLedger(Path(self._ledger_tmp.name) / "events.sqlite3")

    def test_long_messages_are_split_for_telegram(self) -> None:
        calls = []

        def transport(url, payload, timeout):
            calls.append(payload)
            return {"ok": True, "result": {"message_id": len(calls)}}

        client = TelegramApiClient("token", transport=transport)
        result = client.send(TelegramOutbound("chat", "a" * 5000))

        self.assertTrue(result["ok"])
        self.assertEqual(2, len(calls))
        self.assertEqual(4096, len(calls[0]["text"]))
        self.assertEqual(904, len(calls[1]["text"]))

    def test_poller_schedules_auto_delete_for_every_chunk(self):
        scheduled = []

        class Adapter:
            def handle_update(self, _update):
                return TelegramOutbound(
                    "2",
                    "a" * 5000,
                    auto_delete_seconds=30,
                )

            def schedule_tavern_auto_delete(self, chat_id, message_id, seconds):
                scheduled.append((chat_id, message_id, seconds))

        def transport(_url, payload, _timeout):
            message_id = 100 if len(payload["text"]) == 4096 else 101
            return {"ok": True, "result": {"message_id": message_id}}

        client = TelegramApiClient("token", transport=transport)

        class Client:
            token = "test_token"

            def get_updates(self, *, offset=None, timeout_seconds=25):
                return (
                    {
                        "update_id": 7,
                        "message": {
                            "from": {"id": 1},
                            "chat": {"id": 2},
                            "text": "hola",
                        },
                    },
                )

            def send(self, outbound, *, start_chunk=0, on_chunk_ack=None):
                return client.send(
                    outbound,
                    start_chunk=start_chunk,
                    on_chunk_ack=on_chunk_ack,
                )

        poller = TelegramPoller(
            Client(),
            Adapter(),
            event_ledger=self.event_ledger,
            sleeper=lambda _: None,
        )
        result = poller.run(max_cycles=1)

        self.assertEqual(1, result.responses_sent)
        self.assertEqual(
            [("2", 100, 30), ("2", 101, 30)],
            scheduled,
        )

    def test_poller_does_not_advance_offset_when_delivery_fails(self) -> None:
        class Client:
            def __init__(self):
                self.token = "test_token"
                self.calls = 0

            def get_updates(self, *, offset=None, timeout_seconds=25):
                self.calls += 1
                return ({"update_id": 7, "message": {"from": {"id": 1}, "chat": {"id": 2}, "text": "hola"}},)

            def send(self, outbound):
                raise RuntimeError("not used")

        class Adapter:
            def handle_update(self, update):
                return TelegramOutbound("2", "respuesta")

        class FailingClient(Client):
            def send(self, outbound):
                from bot_ia.interfaces.telegram import TelegramTransportError
                raise TelegramTransportError("temporary")

        client = FailingClient()
        poller = TelegramPoller(
            client,
            Adapter(),
            event_ledger=self.event_ledger,
            config=PollingConfig(max_consecutive_failures=1),
            sleeper=lambda _: None,
        )
        result = poller.run(max_cycles=1)

        self.assertEqual(0, result.responses_sent)
        self.assertIsNone(poller.offset)

    def test_delivery_failure_stops_processing_later_updates_in_same_batch(self) -> None:
        class Client:
            def __init__(self):
                self.token = "test_token"
                self.sent = 0

            def get_updates(self, *, offset=None, timeout_seconds=25):
                return (
                    {"update_id": 7, "message": {"from": {"id": 1}, "chat": {"id": 2}, "text": "uno"}},
                    {"update_id": 8, "message": {"from": {"id": 1}, "chat": {"id": 2}, "text": "dos"}},
                )

            def send(self, outbound, *, start_chunk=0):
                self.sent += 1
                from bot_ia.interfaces.telegram import TelegramTransportError
                raise TelegramTransportError("temporary")

        class Adapter:
            def __init__(self):
                self.handled = []

            def handle_update(self, update):
                self.handled.append(update["update_id"])
                return TelegramOutbound("2", f"respuesta {update['update_id']}")

        client = Client()
        adapter = Adapter()
        poller = TelegramPoller(
            client,
            adapter,
            config=PollingConfig(max_consecutive_failures=1),
            sleeper=lambda _: None,
        )
        result = poller.run(max_cycles=1)

        self.assertEqual([7], adapter.handled)
        self.assertEqual(0, result.responses_sent)
        self.assertIsNone(poller.offset)


if __name__ == "__main__":
    unittest.main()
