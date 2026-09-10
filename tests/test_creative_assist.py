import unittest

from bot_ia.core.creative_assist import build_stuck_menu, expand_scene_sketch


class CreativeAssistTests(unittest.TestCase):
    def test_short_sketch_expands_to_twenty_development_questions(self):
        text = expand_scene_sketch("Kuro salva a alguien, camina y se va")
        lines = text.splitlines()
        self.assertEqual(len(lines), 20)
        self.assertIn("¿Por qué Kuro decide intervenir", text)
        self.assertIn("¿Kuro tiene algún sentimiento previo", text)
        self.assertIn("¿Qué consecuencia deja", text)
        self.assertIn("¿Qué debería quedar preparado", text)

    def test_question_limit_is_respected(self):
        text = expand_scene_sketch("Kuro salva a alguien", max_questions=5)
        self.assertEqual(len(text.splitlines()), 5)

    def test_empty_sketch_does_not_invent_a_scene(self):
        text = expand_scene_sketch("   ")
        self.assertIn("Necesito aunque sea unas pocas palabras", text)

    def test_stuck_menu_keeps_expensive_paths_explicit(self):
        menu = build_stuck_menu()
        callbacks = [data for row in menu for _, data in row]
        self.assertEqual(callbacks[:3], ["stuck:local", "stuck:api", "stuck:prompt"])


if __name__ == "__main__":
    unittest.main()
