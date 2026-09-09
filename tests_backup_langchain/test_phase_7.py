from __future__ import annotations

from pathlib import Path
import unittest

from bot_ia.contracts import UniverseDefinition, UniverseRegistry
from bot_ia.core.application import BotApplication, InMemorySessionStore
from bot_ia.core.brain import LocalBrain
from bot_ia.core.router import Router
from bot_ia.interfaces.telegram import TelegramAdapter, TelegramApiClient, TelegramConfigurationError, TelegramInputError, TelegramOutbound, parse_update


def update(text: str, user: int = 7, chat: int = 9) -> dict[str, object]:
    return {"message": {"text": text, "from": {"id": user}, "chat": {"id": chat}}}


class Phase7Tests(unittest.TestCase):
    def setUp(self) -> None:
        universes = UniverseRegistry()
        universes.register(UniverseDefinition("one_neko_punch", "One Neko Punch", Path("data/one")))
        universes.register(UniverseDefinition("other_world", "Other World", Path("data/other")))
        self.sessions = InMemorySessionStore()
        self.adapter = TelegramAdapter(BotApplication(LocalBrain(universes), Router(), self.sessions, default_universe_id="one_neko_punch"))

    def test_update_becomes_normalized_request(self) -> None:
        inbound = parse_update(update("  Hola  "))
        self.assertEqual(("7", "9", "Hola"), (inbound.user_id, inbound.conversation_id, inbound.text))

    def test_response_becomes_telegram_message(self) -> None:
        outgoing = self.adapter.handle_update(update("Hola"))
        self.assertEqual("9", outgoing.chat_id)
        self.assertEqual("local", outgoing.route)

    def test_user_and_conversation_are_identified(self) -> None:
        inbound = parse_update(update("Ayuda", user=11, chat=22))
        self.assertEqual("11", inbound.user_id)
        self.assertEqual("22", inbound.conversation_id)

    def test_state_is_isolated_between_users(self) -> None:
        self.adapter.handle_update(update("Hola", user=1, chat=10))
        self.adapter.handle_update(update("Hola", user=2, chat=10))
        self.assertIsNot(self.sessions.get("1", "10"), self.sessions.get("2", "10"))

    def test_valid_universe_change_updates_only_session(self) -> None:
        self.adapter.handle_update(update("Hola", user=1, chat=10))
        self.adapter.handle_update(update("Hola", user=2, chat=10))
        changed = self.sessions.get("1", "10")
        untouched = self.sessions.get("2", "10")
        changed.chapter_id, changed.active_entity_ids, changed.recent_reference_ids = "chapter-3", ("kuro",), ("ref-1",)
        untouched.chapter_id, untouched.active_entity_ids, untouched.recent_reference_ids = "chapter-8", ("mika",), ("ref-2",)

        self.adapter.handle_update(update("Cambiar al universo other_world", user=1, chat=10))
        self.assertEqual("other_world", changed.universe_id)
        self.assertEqual((), changed.active_entity_ids)
        self.assertEqual((), changed.recent_reference_ids)
        self.assertIsNone(changed.chapter_id)
        self.assertEqual("one_neko_punch", untouched.universe_id)
        self.assertEqual(("mika",), untouched.active_entity_ids)
        self.assertEqual(("ref-2",), untouched.recent_reference_ids)
        self.assertEqual("chapter-8", untouched.chapter_id)

    def test_invalid_update_is_controlled_error(self) -> None:
        with self.assertRaises(TelegramInputError):
            self.adapter.handle_update({"message": {}})

    def test_empty_message_is_rejected(self) -> None:
        with self.assertRaises(TelegramInputError):
            parse_update(update("  "))

    def test_basic_commands_are_local(self) -> None:
        self.assertIn("listo", self.adapter.handle_update(update("/start")).text)
        self.assertIn("Envía", self.adapter.handle_update(update("/help")).text)

    def test_local_route_works_end_to_end(self) -> None:
        response = self.adapter.handle_update(update("Hola"))
        self.assertEqual("local", response.route)
        self.assertIn("procesada", response.text)

    def test_search_agent_and_llm_routes_are_delivered(self) -> None:
        self.assertEqual("search", self.adapter.handle_update(update("Quien es Kuro?")).route)
        self.assertEqual("agent", self.adapter.handle_update(update("Revisa este dialogo")).route)
        self.assertEqual("llm", self.adapter.handle_update(update("Escribe una escena breve")).route)

    def test_telegram_client_uses_only_outbound_payload(self) -> None:
        calls = []
        client = TelegramApiClient("test-token", transport=lambda url, payload, timeout: calls.append((url, payload, timeout)) or {"ok": True})
        client.send(TelegramOutbound("9", "hola"))
        self.assertEqual({"chat_id": "9", "text": "hola"}, calls[0][1])

    def test_missing_token_and_long_message_are_rejected(self) -> None:
        with self.assertRaises(TelegramConfigurationError):
            TelegramApiClient("")
        client = TelegramApiClient("test-token", transport=lambda *_: {"ok": True})
        with self.assertRaises(TelegramInputError):
            client.send(TelegramOutbound("9", "x" * 4097))


if __name__ == "__main__":
    unittest.main()
