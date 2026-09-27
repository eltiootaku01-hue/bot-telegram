# -*- coding: utf-8 -*-
import unittest
import tempfile

from tests.diagnostics.phase1j_keyboardinterrupt import Phase1JRecorder
from pathlib import Path

from bot_ia.interfaces.telegram_event_ledger import TelegramEventLedger
from bot_ia.interfaces.telegram import TelegramAdapter, TelegramApiClient, TelegramOutbound, TelegramPoller, PollingConfig


class TelegramRuntimeSafetyTests(unittest.TestCase):
    def test_adapter_close_stops_xp_writer_thread(self):
        adapter = TelegramAdapter(object())
        recorder = Phase1JRecorder()
        recorder.install(adapter._xp_tracker, adapter)
        self.addCleanup(recorder.uninstall)
        self.addCleanup(adapter.close)
        recorder.log("telegram_adapter_created")
        recorder.log("passive_xp_tracker_created")

        try:
            recorder.log("record_message_call")
            adapter._xp_tracker.record_message("shutdown-test", "telegram")
            recorder.log("record_message_return")
            thread = adapter._xp_tracker._thread
            self.assertIsNotNone(thread)
            self.assertTrue(thread.is_alive())

            recorder.log("adapter_close_call")
            adapter.close()
            recorder.log("adapter_close_return")

            self.assertFalse(
                thread.is_alive(),
                "TelegramAdapter.close() debe detener el escritor XP",
            )
            recorder.log("test_finished")
        except KeyboardInterrupt as error:
            recorder.capture_keyboard_interrupt(error, tracker=adapter._xp_tracker)
            raise

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
