import json
import threading
import unittest
from urllib.request import Request, urlopen

from bot_ia.interfaces.web import WebApi, create_web_server


class FakeApplication:
    def handle(self, request):
        class Route:
            value = "search"

        class Decision:
            route = Route()
            agent_id = "ia_chan"

        class Brain:
            universe_id = "one_neko_punch"

        class Execution:
            searched = True
            provider_response = None

        class Response:
            text = "evidencia"
            decision = Decision()
            brain = Brain()
            execution = Execution()

        return Response()


class WebRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.server = create_web_server(WebApi(FakeApplication(), api_token="t" * 32), port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_health_and_openapi_are_reachable(self):
        with urlopen(self.base + "/health") as response:
            self.assertEqual(200, response.status)
            self.assertTrue(json.loads(response.read())["ok"])
        with urlopen(self.base + "/openapi.json") as response:
            document = json.loads(response.read())
            self.assertEqual("queryBotIA", document["paths"]["/v1/query"]["post"]["operationId"])

    def test_query_requires_bearer_and_returns_json(self):
        body = json.dumps({"message": "hola"}).encode("utf-8")
        request = Request(self.base + "/v1/query", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(Exception):
            urlopen(request)

        request.add_header("Authorization", "Bearer " + "t" * 32)
        with urlopen(request) as response:
            payload = json.loads(response.read())
            self.assertEqual("evidencia", payload["answer"])
            self.assertTrue(payload["searched"])


if __name__ == "__main__":
    unittest.main()
