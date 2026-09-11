import unittest

from bot_ia.core.models import Route
from bot_ia.interfaces.web import (
    ExternalApiAuthorizationError,
    MAX_ID_CHARS,
    MAX_MESSAGE_CHARS,
    WebApi,
    WebApiError,
    openapi_document,
)


class _Decision:
    route = Route.SEARCH
    agent_id = None
    external_api_authorized = False


class _Brain:
    universe_id = "one_neko_punch"


class _Response:
    text = "respuesta local"
    decision = _Decision()
    brain = _Brain()
    execution = None


class _Application:
    def __init__(self):
        self.requests = []

    def handle(self, request):
        self.requests.append(request)
        return _Response()


class WebApiTests(unittest.TestCase):
    def test_query_defaults_to_local_only(self):
        app = _Application()
        result = WebApi(app).query({"message": "hola"})
        self.assertFalse(app.requests[0].allow_external_api)
        self.assertFalse(result["external_api_authorized"])

    def test_query_requires_boolean_for_external_api(self):
        with self.assertRaises(WebApiError):
            WebApi(_Application()).query({"message": "hola", "allow_external_api": "yes"})

    def test_explicit_external_api_flag_reaches_application_when_surface_allows_it(self):
        app = _Application()
        WebApi(app, allow_external_api=True).query({"message": "investiga", "allow_external_api": True})
        self.assertTrue(app.requests[0].allow_external_api)

    def test_remote_external_api_requires_server_side_authorization(self):
        with self.assertRaises(ExternalApiAuthorizationError):
            WebApi(_Application()).query({"message": "investiga", "allow_external_api": True})

    def test_bearer_authorization_is_exact(self):
        api = WebApi(_Application(), api_token="x" * 32)
        self.assertTrue(api.authorize("Bearer " + "x" * 32))
        self.assertFalse(api.authorize("Bearer wrong"))
        self.assertFalse(api.authorize(None))

    def test_message_length_is_bounded(self):
        with self.assertRaises(WebApiError):
            WebApi(_Application()).query({"message": "x" * (MAX_MESSAGE_CHARS + 1)})

    def test_identity_lengths_are_bounded(self):
        with self.assertRaises(WebApiError):
            WebApi(_Application()).query({"message": "hola", "user_id": "u" * (MAX_ID_CHARS + 1)})
        with self.assertRaises(WebApiError):
            WebApi(_Application()).query({"message": "hola", "conversation_id": "c" * (MAX_ID_CHARS + 1)})

    def test_openapi_documents_explicit_api_flag(self):
        schema = openapi_document("https://bot.example")
        properties = schema["components"]["schemas"]["QueryRequest"]["properties"]
        self.assertIn("allow_external_api", properties)
        self.assertFalse(properties["allow_external_api"]["default"])

    def test_openapi_can_describe_enabled_external_api_surface(self):
        schema = openapi_document("https://bot.example", allow_external_api=True)
        description = schema["components"]["schemas"]["QueryRequest"]["properties"]["allow_external_api"]["description"]
        self.assertNotIn("not configured", description)


if __name__ == "__main__":
    unittest.main()
