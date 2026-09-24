# -*- coding: utf-8 -*-
import unittest

from bot_ia.providers.coze import CozeProvider
from bot_ia.providers.errors import MissingApiKeyError
from bot_ia.providers.models import ProviderRequest


class CozeProviderTests(unittest.TestCase):
    def test_provider_contract_remains_callable_without_network(self) -> None:
        provider = CozeProvider(key_loader=lambda _name: None)
        request = ProviderRequest(
            "coze",
            "coze-test",
            "hello",
            32,
            1.0,
            "coze-test",
            "test",
        )
        with self.assertRaises(MissingApiKeyError):
            provider.generate(request)


if __name__ == "__main__":
    unittest.main()
