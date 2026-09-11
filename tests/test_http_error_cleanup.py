import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from bot_ia.providers.adapters import _stdlib_transport
from bot_ia.providers.errors import MissingApiKeyError


class HttpErrorCleanupTests(unittest.TestCase):
    def test_http_error_body_is_closed_before_provider_error_escapes(self) -> None:
        body = io.BytesIO(b"unauthorized")
        error = HTTPError("https://example.invalid", 401, "Unauthorized", {}, body)

        with patch("bot_ia.providers.adapters.urlopen", side_effect=error):
            with self.assertRaises(MissingApiKeyError):
                _stdlib_transport(
                    "https://example.invalid",
                    {},
                    {"input": "test"},
                    1.0,
                )

        self.assertTrue(body.closed)


if __name__ == "__main__":
    unittest.main()
