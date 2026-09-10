import json
import unittest

from bot_ia.interfaces.web import WebApi, openapi_document


class FakeApplication:
    def handle(self, request):
        class Route:
            value = "search"

        class Decision:
            route = Route()
            agent_id = "ia_chan"

        class Brain:
            universe_id = "alpha_world"

        class Provider:
            provider = "fake"

        class Execution:
            searched = True
            provider_response = Provider()

        class Response:
            text = "Kuro protege Alpha."
            decision = Decision()
            brain = Brain()
            execution = Execution()

        return Response()


class WebInterfaceTests(unittest.TestCase):
    def test_query_returns_stable_machine_readable_contract(self):
        api = WebApi(FakeApplication())
        result = api.query({"message": "¿Quién es Kuro?"})
        self.assertEqual("Kuro protege Alpha.", result["answer"])
        self.assertEqual("search", result["route"])
        self.assertEqual("alpha_world", result["universe_id"])
        self.assertTrue(result["searched"])

    def test_invalid_payload_is_rejected(self):
        api = WebApi(FakeApplication())
        with self.assertRaises(ValueError):
            api.query({"message": ""})

    def test_bearer_auth_is_enforced_when_configured(self):
        api = WebApi(FakeApplication(), api_token="secret")
        self.assertFalse(api.authorize(None))
        self.assertFalse(api.authorize("Bearer wrong"))
        self.assertTrue(api.authorize("Bearer secret"))

    def test_openapi_declares_query_operation_and_bearer_security(self):
        document = openapi_document("https://bot.example.test")
        self.assertEqual("3.1.0", document["openapi"])
        operation = document["paths"]["/v1/query"]["post"]
        self.assertEqual("queryBotIA", operation["operationId"])
        self.assertEqual([{"bearerAuth": []}], operation["security"])
        self.assertEqual("https://bot.example.test", document["servers"][0]["url"])

    def test_health_operation_is_exposed(self):
        document = openapi_document("https://bot.example.test")
        operation = document["paths"]["/health"]["get"]
        self.assertEqual("health", operation["operationId"])

    def test_openapi_is_json_serializable(self):
        json.dumps(openapi_document("https://bot.example.test"), ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
