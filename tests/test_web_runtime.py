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

    def setUp(self):
        self.server = create_web_server(WebApi(FakeApplication(), api_token="t" * 32), port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        shutdown_thread = threading.Thread(
            target=self.server.shutdown,
            daemon=True,
        )
        shutdown_thread.start()
        shutdown_thread.join(timeout=3)
        self.assertFalse(
            shutdown_thread.is_alive(),
            "HTTP server shutdown did not complete within 3 seconds",
        )
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_health_and_openapi_are_reachable(self):
        script = r"""
import http.client
import json
import threading

from bot_ia.interfaces.web import WebApi, create_web_server

server = create_web_server(
    WebApi(object(), api_token="t" * 32),
    port=0,
)
thread = threading.Thread(
    target=server.serve_forever,
    daemon=True,
)
thread.start()

try:
    for path in ("/health", "/openapi.json"):
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            server.server_port,
            timeout=3,
        )
        connection.request(
            "GET",
            path,
            headers={"Connection": "close"},
        )
        response = connection.getresponse()
        body = response.read()
        assert response.status == 200, response.status
        payload = json.loads(body)
        if path == "/health":
            assert payload["ok"] is True
        else:
            assert (
                payload["paths"]["/v1/query"]["post"]["operationId"]
                == "queryBotIA"
            )
        connection.close()
finally:
    shutdown_thread = threading.Thread(
        target=server.shutdown,
        daemon=True,
    )
    shutdown_thread.start()
    shutdown_thread.join(timeout=3)
    if shutdown_thread.is_alive():
        raise RuntimeError("child server shutdown timed out")
    server.server_close()
    thread.join(timeout=2)
    if thread.is_alive():
        raise RuntimeError("child server loop did not stop")

        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=os.getcwd(),
        )
        self.assertEqual(
            0,
            completed.returncode,
            completed.stderr or completed.stdout,
        )

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
