import unittest

from bot_ia.core.creative_assist import expand_scene_sketch
from bot_ia.core.application import ApplicationResponse
from bot_ia.interfaces.telegram_ui import TelegramNovelAdapter


class _Decision:
    route = type("Route", (), {"value": "local"})()


class _FakeApp:
    def __init__(self) -> None:
        self.calls = []

    def handle(self, request):
        self.calls.append(request)
        return ApplicationResponse("respuesta", None, _Decision(), None)


class CreativeAssistTests(unittest.TestCase):
    def test_short_sketch_becomes_multiple_action_questions_without_provider(self):
        text = expand_scene_sketch("Kuro salva a alguien, camina y se va")
        self.assertGreaterEqual(text.count("?"), 10)
        self.assertIn("¿Por qué Kuro decide actuar", text)
        self.assertIn("¿A quién ayuda", text)
        self.assertIn("¿La escena termina", text)


class TelegramUiTests(unittest.TestCase):
    def test_main_menu_exposes_novel_and_status_controls(self):
        adapter = TelegramNovelAdapter(_FakeApp())
        labels = [label for row in adapter.MAIN_MENU for label, _ in row]
        self.assertIn("📖 Novela", labels)
        self.assertIn("📊 Estado API", labels)
        self.assertIn("🧰 Destrabar escena", labels)

    def test_local_scene_helper_does_not_call_application(self):
        app = _FakeApp()
        adapter = TelegramNovelAdapter(app)
        update = {"callback_query": {"from": {"id": 1}, "message": {"chat": {"id": 2}}, "data": "stuck:local"}}
        outbound = adapter.handle_callback(update)
        self.assertEqual(app.calls, [])
        self.assertIn("boceto", outbound.text)
        message = {"message": {"from": {"id": 1}, "chat": {"id": 2}, "text": "Kuro salva, camina, se va"}}
        result = adapter.handle_update(message)
        self.assertEqual(app.calls, [])
        self.assertIn("¿A quién ayuda", result.text)

    def test_api_button_requires_explicit_authorization_flag(self):
        app = _FakeApp()
        adapter = TelegramNovelAdapter(app)
        key = ("1", "2")
        adapter._fallback_query[key] = "consulta pendiente"
        adapter._last_message[key] = "mensaje distinto posterior"
        update = {"callback_query": {"from": {"id": 1}, "message": {"chat": {"id": 2}}, "data": "fallback:api"}}
        adapter.handle_callback(update)
        self.assertEqual(len(app.calls), 1)
        self.assertTrue(app.calls[0].allow_external_api)

    def test_prompt_button_never_calls_application(self):
        app = _FakeApp()
        adapter = TelegramNovelAdapter(app)
        adapter._fallback_query[("1", "2")] = "Kuro salva a alguien"
        update = {"callback_query": {"from": {"id": 1}, "message": {"chat": {"id": 2}}, "data": "fallback:prompt"}}
        result = adapter.handle_callback(update)
        self.assertEqual(app.calls, [])
        self.assertIn("PROMPT PARA OTRA IA", result.text)


if __name__ == "__main__":
    unittest.main()
