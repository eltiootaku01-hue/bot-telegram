# -*- coding: utf-8 -*-
import json
import threading
import unittest
from urllib.error import HTTPError
import http.client
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

    def _http_request(self, path, *, method="GET", body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.request(
            method,
            path,
            body=body,
            headers=headers or {},
        )
        return connection

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = create_web_server(
            WebApi(FakeApplication(), api_token="t" * 32),
            port=0,
        )
        cls.thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )
        cls.thread.start()

        connection = http.client.HTTPConnection(
            "127.0.0.1",
            cls.server.server_port,
            timeout=3,
        )
        try:
            connection.request("GET", "/health")
            response = connection.getresponse()
            if response.status != 200:
                raise AssertionError(
                    f"HTTP server readiness failed: {response.status}"
                )
            if not json.loads(response.read())["ok"]:
                raise AssertionError("HTTP server readiness returned ok=false")
        finally:
            connection.close()

    @classmethod
    def tearDownClass(cls):
        shutdown_thread = threading.Thread(
            target=cls.server.shutdown,
            daemon=True,
        )
        shutdown_thread.start()
        shutdown_thread.join(timeout=3)
        if shutdown_thread.is_alive():
            raise AssertionError(
                "HTTP server shutdown did not complete within 3 seconds"
            )
        cls.server.server_close()
        cls.thread.join(timeout=2)
        if cls.thread.is_alive():
            raise AssertionError(
                "HTTP server thread did not terminate within 2 seconds"
            )
        super().tearDownClass()

    def setUp(self):
        self.server = type(self).server
        self.thread = type(self).thread
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def test_health_and_openapi_are_reachable(self):
        connection = self._http_request("/health")
        try:
            response = connection.getresponse()
            self.assertEqual(200, response.status)
            self.assertTrue(json.loads(response.read())["ok"])
        finally:
            connection.close()
        connection = self._http_request("/openapi.json")
        try:
            response = connection.getresponse()
            document = json.loads(response.read())
            self.assertEqual("queryBotIA", document["paths"]["/v1/query"]["post"]["operationId"])
        finally:
            connection.close()

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
