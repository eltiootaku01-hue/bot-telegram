# -*- coding: utf-8 -*-
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from bot_ia.interfaces.web import BoundedThreadingHTTPServer, WebApi, WebApiError, create_web_server


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
    _opener = build_opener(ProxyHandler({}))

    @classmethod
    def _open(cls, url, *, data=None, headers=None, method=None):
        return cls._opener.open(
            Request(
                url,
                data=data,
                headers=headers or {},
                method=method,
            ),
            timeout=3,
        )

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
        with self._open(self.base + "/health") as response:
            self.assertEqual(200, response.status)
            self.assertTrue(json.loads(response.read())["ok"])
        with self._open(self.base + "/openapi.json") as response:
            document = json.loads(response.read())
            self.assertEqual("queryBotIA", document["paths"]["/v1/query"]["post"]["operationId"])

    def test_query_requires_bearer_and_returns_json(self):
        body = json.dumps({"message": "hola"}).encode("utf-8")
        request = Request(self.base + "/v1/query", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(HTTPError) as raised:
            self._opener.open(request, timeout=3)
        raised.exception.close()

        request.add_header("Authorization", "Bearer " + "t" * 32)
        with self._opener.open(request, timeout=3) as response:
            payload = json.loads(response.read())
            self.assertEqual("evidencia", payload["answer"])
            self.assertTrue(payload["searched"])

    def test_non_loopback_binding_requires_api_token(self):
        with self.assertRaises(WebApiError):
            create_web_server(WebApi(FakeApplication()), host="0.0.0.0", port=0)

    def test_non_loopback_binding_is_allowed_with_api_token(self):
        server = create_web_server(WebApi(FakeApplication(), api_token="t" * 32), host="0.0.0.0", port=0)
        server.server_close()

    def test_web_server_has_bounded_request_concurrency(self):
        server = create_web_server(WebApi(FakeApplication()), port=0)
        try:
            self.assertIsInstance(server, BoundedThreadingHTTPServer)
            self.assertEqual(8, server.max_workers)
        finally:
            server.server_close()


if __name__ == "__main__":
    unittest.main()
