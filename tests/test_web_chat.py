import unittest

from bot_ia.interfaces.web_chat import CHAT_HTML


class WebChatSurfaceTests(unittest.TestCase):
    def test_chat_surface_is_mobile_and_local_first(self):
        self.assertIn('viewport-fit=cover', CHAT_HTML)
        self.assertIn("/v1/query", CHAT_HTML)
        self.assertIn("localStorage", CHAT_HTML)
        self.assertIn("Authorization", CHAT_HTML)


if __name__ == "__main__":
    unittest.main()
