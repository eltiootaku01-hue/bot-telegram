from __future__ import annotations

import unittest

from bot_ia.core.context_destinations import get_context_destination, list_context_destinations


class ContextDestinationTests(unittest.TestCase):
    def test_chatgpt_is_an_explicit_approved_destination(self) -> None:
        destination = get_context_destination("chatgpt")
        self.assertEqual(destination.display_name, "ChatGPT")
        self.assertEqual(destination.url, "https://chatgpt.com/")

    def test_destination_registry_is_not_empty(self) -> None:
        self.assertTrue(list_context_destinations())

    def test_unknown_destination_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            get_context_destination("arbitrary-url")


if __name__ == "__main__":
    unittest.main()
