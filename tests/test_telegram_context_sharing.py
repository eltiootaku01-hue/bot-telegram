from __future__ import annotations

import unittest
from unittest.mock import patch

from bot_ia.core.application import ApplicationResponse
from bot_ia.interfaces.telegram_ui import TelegramNovelAdapter


class _Decision:
    route = type("Route", (), {"value": "local"})()


class _Evidence:
    class Query:
        universe_id = "one_neko_punch"

    query = Query()


class _Execution:
    evidence = _Evidence()


class _FakeApp:
    def __init__(self) -> None:
        self.calls = []

    def handle(self, request):
        self.calls.append(request)
        return ApplicationResponse("respuesta", None, _Decision(), _Execution())


class _Shared:
    def __init__(self, source_ids):
        self.source_ids = tuple(source_ids)

    def as_external_prompt(self):
        return "PROMPT\nFUENTES: " + ", ".join(self.source_ids)


class TelegramContextSharingTests(unittest.TestCase):
    def test_share_menu_requires_a_previous_execution(self):
        adapter = TelegramNovelAdapter(_FakeApp())
        update = {"callback_query": {"from": {"id": 1}, "message": {"chat": {"id": 2}}, "data": "menu:share_context"}}
        result = adapter.handle_callback(update)
        self.assertIn("No hay una consulta procesada", result.text)

    def test_main_menu_exposes_context_sharing(self):
        adapter = TelegramNovelAdapter(_FakeApp())
        labels = [label for row in adapter.MAIN_MENU for label, _ in row]
        self.assertIn("🔗 Compartir contexto", labels)

    def test_context_menu_starts_with_all_retrieved_sources_selected(self):
        adapter = TelegramNovelAdapter(_FakeApp())
        key = ("1", "2")
        adapter._last_execution[key] = _Execution()
        with patch("bot_ia.interfaces.telegram_ui.available_context_sources", return_value=("canon_a", "canon_b")):
            result = adapter.handle_callback({"callback_query": {"from": {"id": 1}, "message": {"chat": {"id": 2}}, "data": "menu:share_context"}})
        self.assertEqual(adapter._context_selection[key], {0, 1})
        labels = [label for row in result.keyboard for label, _ in row]
        self.assertTrue(any("2/2" in label for label in labels))

    def test_toggle_then_send_uses_only_selected_retrieved_source(self):
        adapter = TelegramNovelAdapter(_FakeApp())
        key = ("1", "2")
        adapter._last_execution[key] = _Execution()
        with patch("bot_ia.interfaces.telegram_ui.available_context_sources", return_value=("canon_a", "canon_b")), patch("bot_ia.interfaces.telegram_ui.select_context_sources", side_effect=lambda execution, ids: (execution, tuple(ids))), patch("bot_ia.interfaces.telegram_ui.build_shared_context", side_effect=lambda selected: _Shared(selected[1])) as builder:
            adapter.handle_callback({"callback_query": {"from": {"id": 1}, "message": {"chat": {"id": 2}}, "data": "menu:share_context"}})
            adapter.handle_callback({"callback_query": {"from": {"id": 1}, "message": {"chat": {"id": 2}}, "data": "context:toggle:0"}})
            result = adapter.handle_callback({"callback_query": {"from": {"id": 1}, "message": {"chat": {"id": 2}}, "data": "context:send"}})
        self.assertIn("FUENTES: canon_b", result.text)
        self.assertNotIn("canon_a", result.text)
        builder.assert_called_once()
        self.assertIsNone(adapter._context_selection.get(key))

    def test_out_of_range_source_index_is_rejected(self):
        adapter = TelegramNovelAdapter(_FakeApp())
        key = ("1", "2")
        adapter._last_execution[key] = _Execution()
        with patch("bot_ia.interfaces.telegram_ui.available_context_sources", return_value=("canon_a",)):
            with self.assertRaises(ValueError):
                adapter.handle_callback({"callback_query": {"from": {"id": 1}, "message": {"chat": {"id": 2}}, "data": "context:toggle:9"}})


if __name__ == "__main__":
    unittest.main()
