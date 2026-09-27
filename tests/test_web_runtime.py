# -*- coding: utf-8 -*-
import json
import os
import platform
import sys
import threading
import traceback
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
    _forensic_history = []

    def _forensic_phase(self, phase):
        self._forensic_history.append(
            {
                "phase": phase,
                "pid": os.getpid(),
                "server_alive": getattr(self, "thread", None).is_alive() if getattr(self, "thread", None) else None,
                "server_shutdown_requested": (
                    getattr(self.server, "_BaseServer__shutdown_request", None)
                    if getattr(self, "server", None)
                    else None
                ),
            }
        )

    def _forensic_capture_10053(self, error):
        winerror = getattr(error, "winerror", None)
        errno = getattr(error, "errno", None)
        if winerror != 10053:
            return
        server = getattr(self, "server", None)
        server_socket = getattr(server, "socket", None)
        socket_state = {}
        if server_socket is not None:
            socket_state["fileno"] = server_socket.fileno()
            socket_state["closed"] = getattr(server_socket, "_closed", None)
            socket_state["family"] = str(getattr(server_socket, "family", None))
            socket_state["type"] = str(getattr(server_socket, "type", None))
            try:
                socket_state["getsockname"] = repr(server_socket.getsockname())
            except OSError as exc:
                socket_state["getsockname_error"] = repr(exc)
            try:
                socket_state["so_error"] = server_socket.getsockopt(
                    __import__("socket").SOL_SOCKET,
                    __import__("socket").SO_ERROR,
                )
            except OSError as exc:
                socket_state["so_error_error"] = repr(exc)

        print("\n=== PHASE 1F FORENSIC: WINERROR 10053 ===", flush=True)
        print(f"PID={os.getpid()}", flush=True)
        print(f"Python={sys.version}", flush=True)
        print(f"Windows={platform.platform()}", flush=True)
        print(
            "GitHubRunner="
            + repr(
                {
                    key: os.environ.get(key)
                    for key in ("RUNNER_OS", "RUNNER_ARCH", "RUNNER_NAME", "GITHUB_RUN_ID", "GITHUB_JOB")
                }
            ),
            flush=True,
        )
        print(f"ExceptionType={type(error).__name__}", flush=True)
        print(f"errno={errno}", flush=True)
        print(f"winerror={winerror}", flush=True)
        print("ServerClass=" + (type(server).__name__ if server else "None"), flush=True)
        print("ServerAddress=" + repr(getattr(server, "server_address", None)), flush=True)
        print("ServerSocket=" + repr(socket_state), flush=True)
        print(
            "ServeForeverThread="
            + repr(
                {
                    "name": getattr(getattr(self, "thread", None), "name", None),
                    "ident": getattr(getattr(self, "thread", None), "ident", None),
                    "daemon": getattr(getattr(self, "thread", None), "daemon", None),
                    "alive": getattr(self.thread, "is_alive", lambda: None)(),
                }
            ),
            flush=True,
        )
        print("CurrentThreads=", flush=True)
        frames = sys._current_frames()
        for thread in threading.enumerate():
            print(
                repr(
                    {
                        "name": thread.name,
                        "ident": thread.ident,
                        "daemon": thread.daemon,
                        "alive": thread.is_alive(),
                    }
                ),
                flush=True,
            )
            frame = frames.get(thread.ident)
            if frame is not None:
                print("".join(traceback.format_stack(frame)), flush=True)
        print("ForensicPhaseHistory=" + repr(self._forensic_history), flush=True)
        print("FullTraceback:", flush=True)
        print("".join(traceback.format_exception(type(error), error, error.__traceback__)), flush=True)
        print("=== END PHASE 1F FORENSIC ===\n", flush=True)

    def _forensic_open(self, request, *, timeout=3):
        self._forensic_phase("before client open")
        try:
            response = self._opener.open(request, timeout=timeout)
            self._forensic_phase("client open returned")
            return response
        except OSError as error:
            self._forensic_capture_10053(error)
            raise

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
        self._forensic_history = []
        self._forensic_phase("before server creation")
        self.server = create_web_server(WebApi(FakeApplication(), api_token="t" * 32), port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._forensic_phase("before serve_forever thread start")
        self.thread.start()
        self._forensic_phase("after serve_forever thread start")
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self._forensic_phase("tearDown before shutdown")
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
        self._forensic_phase("tearDown before server_close")
        self.server.server_close()
        self._forensic_phase("tearDown after server_close")
        self.thread.join(timeout=2)
        self._forensic_phase("tearDown after serve_forever join")

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
            self._forensic_open(request, timeout=3)
        raised.exception.close()

        request.add_header("Authorization", "Bearer " + "t" * 32)
        response = self._forensic_open(request, timeout=3)
        with response:
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
