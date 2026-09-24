# -*- coding: utf-8 -*-
import threading
import unittest

from bot_ia.providers.coze import CozeProvider
from bot_ia.providers.errors import MissingApiKeyError, ProviderRemoteError
from bot_ia.providers.models import ProviderRequest


class CozeThreadSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = CozeProvider(
            key_loader=lambda _name: None,
            enabled=True,
        )
        self.request = ProviderRequest(
            "coze",
            "coze-test",
            "hello",
            32,
            1.0,
            "coze-thread-test",
            "test",
        )

    def test_generate_fails_closed_on_main_thread(self) -> None:
        with self.assertRaises(ProviderRemoteError):
            self.provider.generate(self.request)

    def test_generate_can_enter_provider_logic_from_worker_thread(self) -> None:
        errors: list[BaseException] = []

        def run() -> None:
            try:
                self.provider.generate(self.request)
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=run, name="coze-test-worker")
        thread.start()
        thread.join(2.0)

        self.assertFalse(thread.is_alive(), "worker test thread did not finish")
        self.assertEqual(1, len(errors))
        self.assertIsInstance(errors[0], MissingApiKeyError)


if __name__ == "__main__":
    unittest.main()
