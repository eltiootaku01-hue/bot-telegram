from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
from urllib.error import HTTPError

from bot_ia.contracts import UniverseDefinition, UniverseRegistry
from bot_ia.core.application import BotApplication, InMemorySessionStore
from bot_ia.core.brain import LocalBrain
from bot_ia.core.router import Router
from bot_ia.interfaces.telegram_event_ledger import TelegramEventLedger
from bot_ia.interfaces.telegram import PollingConfig, TelegramAdapter, TelegramApiClient, TelegramApiError, TelegramHttpError, TelegramPoller, TelegramTransportError, _http_post


def update(update_id: int, text: str, user: int = 7, chat: int = 9) -> dict[str, object]:
    return {"update_id": update_id, "message": {"text": text, "from": {"id": user}, "chat": {"id": chat}}}


class Phase72Tests(unittest.TestCase):
    def setUp(self) -> None:
        universes = UniverseRegistry()
        universes.register(UniverseDefinition("one_neko_punch", "One Neko Punch", Path("data/one")))
        universes.register(UniverseDefinition("other_world", "Other World", Path("data/other")))
        self.sessions = InMemorySessionStore()
        self._ledger_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._ledger_tmp.cleanup)
        self.event_ledger = TelegramEventLedger(Path(self._ledger_tmp.name) / "events.sqlite3")
        self.adapter = TelegramAdapter(BotApplication(LocalBrain(universes), Router(), self.sessions, default_universe_id="one_neko_punch"))

    def client(self, transport, **kwargs) -> TelegramApiClient:
        kwargs.setdefault("sleeper", lambda _: None)
        return TelegramApiClient("local-test-token", transport=transport, **kwargs)

    def test_get_updates_returns_multiple_updates_and_sends_offset(self) -> None:
        calls = []
        client = self.client(lambda url, payload, timeout: calls.append((url, payload, timeout)) or {"ok": True, "result": [update(4, "Hola"), update(5, "Ayuda")]})
        self.assertEqual((4, 5), tuple(item["update_id"] for item in client.get_updates(offset=4, timeout_seconds=20)))
        self.assertEqual({"offset": 4, "timeout": 20}, calls[0][1])
        self.assertGreaterEqual(calls[0][2], 25)

    def test_offset_advances_and_duplicate_update_is_not_processed_twice(self) -> None:
        sent, calls = [], []
        batches = [[update(10, "Hola")], [update(10, "Hola")]]
        def transport(url, payload, timeout):
            calls.append(payload)
            if url.endswith("getUpdates"):
                return {"ok": True, "result": batches.pop(0)}
            sent.append(payload)
            return {"ok": True, "result": {}}
        poller = TelegramPoller(self.client(transport), self.adapter, sleeper=lambda _: None, event_ledger=self.event_ledger)
        result = poller.run(max_cycles=2)
        self.assertEqual(11, poller.offset)
        self.assertEqual(1, result.updates_processed)
        self.assertEqual(1, result.updates_skipped)
        self.assertEqual(1, len(sent))
        self.assertEqual(11, calls[2]["offset"])

    def test_transport_error_is_retried_by_poller(self) -> None:
        calls, waits = [], []
        def transport(url, payload, timeout):
            calls.append(payload)
            if len(calls) == 1:
                raise TimeoutError("local timeout")
            return {"ok": True, "result": []}
        poller = TelegramPoller(self.client(transport, max_retries=0), self.adapter, config=PollingConfig(retry_delay_seconds=3), sleeper=waits.append, event_ledger=self.event_ledger)
        result = poller.run(max_cycles=2)
        self.assertEqual(1, result.transport_errors)
        self.assertEqual(1, result.polls)
        self.assertEqual([3, 1.0], waits)

    def test_timeout_is_retried_by_client_with_controlled_delay(self) -> None:
        attempts, waits = [], []
        def transport(url, payload, timeout):
            attempts.append(payload)
            if len(attempts) == 1:
                raise TimeoutError("local timeout")
            return {"ok": True, "result": []}
        self.client(transport, max_retries=1, retry_delay_seconds=0.5, sleeper=waits.append).get_updates()
        self.assertEqual(2, len(attempts))
        self.assertEqual([0.5], waits)

    def test_http_api_error_is_typed_and_not_retried(self) -> None:
        client = self.client(lambda *_: {"ok": False, "description": "bad request"}, max_retries=2)
        with self.assertRaises(TelegramApiError):
            client.get_updates()

    def test_http_status_error_is_wrapped_without_network_access(self) -> None:
        with patch("bot_ia.interfaces.telegram.urlopen", side_effect=HTTPError("https://example.invalid", 502, "bad gateway", {}, None)):
            with self.assertRaises(TelegramHttpError):
                _http_post("https://example.invalid", {}, 1)

    def test_response_is_sent_as_send_message_payload(self) -> None:
        payloads = []
        client = self.client(lambda url, payload, timeout: payloads.append(payload) or {"ok": True})
        poller = TelegramPoller(client, self.adapter, sleeper=lambda _: None)
        result = poller.run(max_cycles=0)
        self.assertEqual(0, result.responses_sent)
        client.send(self.adapter.handle_update(update(1, "Hola")))
        self.assertEqual({"chat_id": "9", "text": "Solicitud local procesada."}, payloads[0])

    def test_user_and_conversation_reach_application(self) -> None:
        sent = []
        def transport(url, payload, timeout):
            if url.endswith("getUpdates"):
                return {"ok": True, "result": [update(3, "Hola", user=11, chat=22)]}
            sent.append(payload)
            return {"ok": True}
        TelegramPoller(self.client(transport), self.adapter, sleeper=lambda _: None, event_ledger=self.event_ledger).run(max_cycles=1)
        self.assertIsNotNone(self.sessions.get("11", "22"))
        self.assertEqual("22", sent[0]["chat_id"])

    def test_sessions_remain_isolated_in_polling(self) -> None:
        def transport(url, payload, timeout):
            if url.endswith("getUpdates"):
                return {"ok": True, "result": [update(1, "Cambiar al universo other_world", user=1, chat=10), update(2, "Hola", user=2, chat=10)]}
            return {"ok": True}
        TelegramPoller(self.client(transport), self.adapter, sleeper=lambda _: None, event_ledger=self.event_ledger).run(max_cycles=1)
        self.assertEqual("other_world", self.sessions.get("1", "10").universe_id)
        self.assertEqual("one_neko_punch", self.sessions.get("2", "10").universe_id)

    def test_stop_closes_polling_cleanly(self) -> None:
        poller = TelegramPoller(self.client(lambda *_: self.fail("transport must not run")), self.adapter, sleeper=lambda _: None, event_ledger=self.event_ledger)
        poller.stop()
        result = poller.run()
        self.assertTrue(result.stopped)
        self.assertEqual(0, result.polls)

    def test_invalid_message_is_skipped_and_next_update_is_processed(self) -> None:
        sent = []
        def transport(url, payload, timeout):
            if url.endswith("getUpdates"):
                return {"ok": True, "result": [update(1, " "), update(2, "Hola")]}
            sent.append(payload)
            return {"ok": True}
        result = TelegramPoller(self.client(transport), self.adapter, sleeper=lambda _: None, event_ledger=self.event_ledger).run(max_cycles=1)
        self.assertEqual(1, result.updates_skipped)
        self.assertEqual(1, result.updates_processed)
        self.assertEqual(1, len(sent))

    def test_local_route_completes_end_to_end_with_fake_telegram(self) -> None:
        sent = []
        def transport(url, payload, timeout):
            if url.endswith("getUpdates"):
                return {"ok": True, "result": [update(8, "Hola", user=5, chat=6)]}
            sent.append(payload)
            return {"ok": True}
        result = TelegramPoller(self.client(transport), self.adapter, sleeper=lambda _: None, event_ledger=self.event_ledger).run(max_cycles=1)
        self.assertEqual(1, result.responses_sent)
        self.assertEqual({"chat_id": "6", "text": "Solicitud local procesada."}, sent[0])
        self.assertIsNotNone(self.sessions.get("5", "6"))

    def test_exhausted_transport_retries_are_controlled(self) -> None:
        client = self.client(lambda *_: (_ for _ in ()).throw(TimeoutError("local timeout")), max_retries=1)
        with self.assertRaises(TelegramTransportError):
            client.get_updates()


if __name__ == "__main__":
    unittest.main()
