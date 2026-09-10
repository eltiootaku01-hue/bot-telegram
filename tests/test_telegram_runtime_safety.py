import unittest

from bot_ia.interfaces.telegram import TelegramApiClient, TelegramOutbound, TelegramPoller, PollingConfig


class TelegramRuntimeSafetyTests(unittest.TestCase):
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

    def test_poller_does_not_advance_offset_when_delivery_fails(self) -> None:
        class Client:
            def __init__(self):
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
            config=PollingConfig(max_consecutive_failures=1),
            sleeper=lambda _: None,
        )
        result = poller.run(max_cycles=1)

        self.assertEqual(0, result.responses_sent)
        self.assertIsNone(poller.offset)


if __name__ == "__main__":
    unittest.main()
