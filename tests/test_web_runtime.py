# -*- coding: utf-8 -*-
import http.client
import json
import os
import platform
import sys
import threading
import time
import traceback
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


class _Phase1HWriteProbe:
    def __init__(self, wrapped, log, request_number, handler):
        self._wrapped = wrapped
        self._log = log
        self._request_number = request_number
        self._handler = handler

    def write(self, data):
        written = self._wrapped.write(data)
        if getattr(self._handler, "_phase1h_headers_finished", False):
            self._log(
                "response_body_sent",
                request_number=self._request_number,
                bytes_written=written,
            )
        return written

    def flush(self):
        return self._wrapped.flush()

    def close(self):
        return self._wrapped.close()

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


class WebRuntimeTests(unittest.TestCase):
    _opener = build_opener(ProxyHandler({}))
    _phase1h_enabled = os.environ.get("PHASE1H_FORENSICS") == "1"

    def _phase1h_log(self, event, **fields):
        if not self._phase1h_enabled:
            return
        record = {
            "monotonic": time.monotonic(),
            "event": event,
            **fields,
        }
        with self._phase1h_lock:
            self._phase1h_events.append(record)

    def _phase1h_endpoint_state(self, sock):
        state = {
            "fileno": None,
            "family": None,
            "type": None,
            "local_endpoint": None,
            "remote_endpoint": None,
        }
        try:
            state["fileno"] = sock.fileno()
        except OSError:
            pass
        try:
            state["family"] = str(sock.family)
        except OSError:
            pass
        try:
            state["type"] = str(sock.type)
        except OSError:
            pass
        try:
            state["local_endpoint"] = repr(sock.getsockname())
        except OSError as error:
            state["local_endpoint"] = f"<error {type(error).__name__}: {error}>"
        try:
            state["remote_endpoint"] = repr(sock.getpeername())
        except OSError as error:
            state["remote_endpoint"] = f"<error {type(error).__name__}: {error}>"
        return state

    def _phase1h_thread_snapshot(self):
        frames = sys._current_frames()
        threads = []
        for thread in threading.enumerate():
            item = {
                "name": thread.name,
                "ident": thread.ident,
                "daemon": thread.daemon,
                "alive": thread.is_alive(),
                "stack": [],
            }
            frame = frames.get(thread.ident)
            if frame is not None:
                item["stack"] = traceback.format_stack(frame)
            threads.append(item)
        return threads

    def _phase1h_capture_failure(self, error):
        if not self._phase1h_enabled:
            return
        self._phase1h_failed = True
        self._phase1h_failure = {
            "type": type(error).__name__,
            "message": str(error),
            "errno": getattr(error, "errno", None),
            "winerror": getattr(error, "winerror", None),
            "traceback": traceback.format_exc(),
            "pid": os.getpid(),
            "thread": {
                "name": threading.current_thread().name,
                "ident": threading.get_ident(),
            },
            "threads": self._phase1h_thread_snapshot(),
        }
        self._phase1h_write_artifact()

    def _phase1h_write_artifact(self):
        if not self._phase1h_enabled:
            return
        os.makedirs("phase1h-artifacts", exist_ok=True)
        artifact = {
            "environment": {
                "python_version": sys.version,
                "python_implementation": platform.python_implementation(),
                "platform": platform.platform(),
                "windows_version": platform.win32_ver() if os.name == "nt" else None,
                "pid": os.getpid(),
                "hostname": platform.node(),
            },
            "failure": self._phase1h_failure,
            "events": list(self._phase1h_events),
        }
        with open(
            "phase1h-artifacts/win10053-forensics.json",
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(artifact, handle, ensure_ascii=False, indent=2, default=str)

    def _phase1h_patch_client(self):
        if not self._phase1h_enabled:
            return
        original = {
            "connect": http.client.HTTPConnection.connect,
            "putrequest": http.client.HTTPConnection.putrequest,
            "endheaders": http.client.HTTPConnection.endheaders,
            "getresponse": http.client.HTTPConnection.getresponse,
            "read": http.client.HTTPResponse.read,
        }
        self._phase1h_original_client = original
        local = threading.local()

        def connect(connection):
            result = original["connect"](connection)
            self._phase1h_log(
                "connection_established",
                request_number=getattr(local, "request_number", None),
                connection_id=id(connection),
            )
            return result

        def putrequest(connection, method, url, skip_host=False, skip_accept_encoding=False):
            self._phase1h_log(
                "request_started",
                request_number=getattr(local, "request_number", None),
                connection_id=id(connection),
                method=method,
                path=url,
            )
            return original["putrequest"](
                connection,
                method,
                url,
                skip_host=skip_host,
                skip_accept_encoding=skip_accept_encoding,
            )

        def endheaders(connection, message_body=None, *, encode_chunked=False):
            result = original["endheaders"](
                connection,
                message_body=message_body,
                encode_chunked=encode_chunked,
            )
            self._phase1h_log(
                "headers_sent",
                request_number=getattr(local, "request_number", None),
                connection_id=id(connection),
            )
            return result

        def getresponse(connection):
            try:
                response = original["getresponse"](connection)
            except BaseException as error:
                self._phase1h_log(
                    "response_exception",
                    request_number=getattr(local, "request_number", None),
                    connection_id=id(connection),
                    exception_type=type(error).__name__,
                    errno=getattr(error, "errno", None),
                    winerror=getattr(error, "winerror", None),
                    message=str(error),
                )
                raise
            self._phase1h_log(
                "response_received",
                request_number=getattr(local, "request_number", None),
                connection_id=id(connection),
                status=response.status,
                reason=response.reason,
            )
            return response

        def read(response, amt=None):
            try:
                data = original["read"](response, amt)
            except BaseException as error:
                self._phase1h_log(
                    "body_receive_exception",
                    request_number=getattr(local, "request_number", None),
                    exception_type=type(error).__name__,
                    errno=getattr(error, "errno", None),
                    winerror=getattr(error, "winerror", None),
                    message=str(error),
                )
                raise
            self._phase1h_log(
                "body_received",
                request_number=getattr(local, "request_number", None),
                bytes_received=len(data),
            )
            return data

        http.client.HTTPConnection.connect = connect
        http.client.HTTPConnection.putrequest = putrequest
        http.client.HTTPConnection.endheaders = endheaders
        http.client.HTTPConnection.getresponse = getresponse
        http.client.HTTPResponse.read = read
        self._phase1h_client_local = local

    def _phase1h_restore_client(self):
        original = getattr(self, "_phase1h_original_client", None)
        if not original:
            return
        http.client.HTTPConnection.connect = original["connect"]
        http.client.HTTPConnection.putrequest = original["putrequest"]
        http.client.HTTPConnection.endheaders = original["endheaders"]
        http.client.HTTPConnection.getresponse = original["getresponse"]
        http.client.HTTPResponse.read = original["read"]

    def _phase1h_instrument_server(self):
        if not self._phase1h_enabled:
            return
        original = {
            "finish_request": self.server.finish_request,
            "handle_error": self.server.handle_error,
            "shutdown": self.server.shutdown,
            "server_close": self.server.server_close,
        }

        def finish_request(request, client_address):
            request_number = self._phase1h_request_counter + 1
            self._phase1h_request_counter = request_number
            state = self._phase1h_endpoint_state(request)
            self._phase1h_log(
                "request_received",
                request_number=request_number,
                thread_name=threading.current_thread().name,
                thread_ident=threading.get_ident(),
                socket=state,
            )
            try:
                result = original["finish_request"](request, client_address)
            except BaseException as error:
                self._phase1h_log(
                    "handler_exception",
                    request_number=request_number,
                    thread_name=threading.current_thread().name,
                    thread_ident=threading.get_ident(),
                    exception_type=type(error).__name__,
                    errno=getattr(error, "errno", None),
                    winerror=getattr(error, "winerror", None),
                    message=str(error),
                    traceback=traceback.format_exc(),
                )
                raise
            finally:
                self._phase1h_log(
                    "request_handler_finished",
                    request_number=request_number,
                    thread_name=threading.current_thread().name,
                    thread_ident=threading.get_ident(),
                )
            return result

        def handle_error(request, client_address):
            state = self._phase1h_endpoint_state(request)
            self._phase1h_log(
                "server_handle_error",
                thread_name=threading.current_thread().name,
                thread_ident=threading.get_ident(),
                socket=state,
            )
            return original["handle_error"](request, client_address)

        def shutdown():
            self._phase1h_log("server_shutdown")
            try:
                return original["shutdown"]()
            finally:
                self._phase1h_log("server_shutdown_returned")

        def server_close():
            self._phase1h_log("server_close")
            try:
                return original["server_close"]()
            finally:
                self._phase1h_log("server_close_returned")

        self.server.finish_request = finish_request
        self.server.handle_error = handle_error
        self.server.shutdown = shutdown
        self.server.server_close = server_close

    def _phase1h_patch_handler_base(self):
        if not self._phase1h_enabled:
            return
        from http.server import BaseHTTPRequestHandler

        original = {
            "setup": BaseHTTPRequestHandler.setup,
            "handle_one_request": BaseHTTPRequestHandler.handle_one_request,
            "send_response": BaseHTTPRequestHandler.send_response,
            "end_headers": BaseHTTPRequestHandler.end_headers,
        }
        self._phase1h_original_handler = original

        def setup(handler):
            result = original["setup"](handler)
            request_number = self._phase1h_request_counter + 1
            handler._phase1h_request_number = request_number
            handler._phase1h_headers_finished = False
            handler.wfile = _Phase1HWriteProbe(
                handler.wfile,
                self._phase1h_log,
                request_number,
                handler,
            )
            state = self._phase1h_endpoint_state(handler.connection)
            self._phase1h_log(
                "request_handler_started",
                request_number=request_number,
                thread_name=threading.current_thread().name,
                thread_ident=threading.get_ident(),
                socket=state,
            )
            return result

        def handle_one_request(handler):
            self._phase1h_log(
                "request_received_by_handler",
                request_number=getattr(handler, "_phase1h_request_number", None),
                thread_name=threading.current_thread().name,
                thread_ident=threading.get_ident(),
            )
            return original["handle_one_request"](handler)

        def send_response(handler, code, message=None):
            self._phase1h_log(
                "response_headers_prepared",
                request_number=getattr(handler, "_phase1h_request_number", None),
                status=code,
            )
            return original["send_response"](handler, code, message)

        def end_headers(handler):
            result = original["end_headers"](handler)
            handler._phase1h_headers_finished = True
            self._phase1h_log(
                "response_headers_sent",
                request_number=getattr(handler, "_phase1h_request_number", None),
            )
            return result

        BaseHTTPRequestHandler.setup = setup
        BaseHTTPRequestHandler.handle_one_request = handle_one_request
        BaseHTTPRequestHandler.send_response = send_response
        BaseHTTPRequestHandler.end_headers = end_headers

    def _phase1h_restore_handler_base(self):
        original = getattr(self, "_phase1h_original_handler", None)
        if not original:
            return
        from http.server import BaseHTTPRequestHandler

        BaseHTTPRequestHandler.setup = original["setup"]
        BaseHTTPRequestHandler.handle_one_request = original["handle_one_request"]
        BaseHTTPRequestHandler.send_response = original["send_response"]
        BaseHTTPRequestHandler.end_headers = original["end_headers"]

    def _phase1h_request_scope(self, request_number):
        if not self._phase1h_enabled:
            return
        self._phase1h_client_local.request_number = request_number

    def _phase1h_run_lifecycle(self, action):
        self._phase1h_log(f"client_{action}_begin")
        try:
            return action()
        except BaseException as error:
            self._phase1h_capture_failure(error)
            raise
        finally:
            self._phase1h_log(f"client_{action}_end")

    def _http_request(self, path, *, method="GET", body=None, headers=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            self.server.server_port,
            timeout=3,
        )
        connection.request(
            method,
            path,
            body=body,
            headers=headers or {},
        )
        return connection

    def setUp(self):
        self._phase1h_lock = threading.Lock()
        self._phase1h_events = []
        self._phase1h_failed = False
        self._phase1h_failure = None
        self._phase1h_request_counter = 0
        self._phase1h_patch_client()
        self.server = create_web_server(WebApi(FakeApplication(), api_token="t" * 32), port=0)
        self._phase1h_log(
            "server_created",
            server_address=repr(self.server.server_address),
            server_port=self.server.server_port,
        )
        self._phase1h_instrument_server()
        self._phase1h_patch_handler_base()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name="phase1h-serve_forever")
        self.thread.start()
        self._phase1h_log(
            "server_thread_started",
            thread_name=self.thread.name,
            thread_ident=self.thread.ident,
            daemon=self.thread.daemon,
            alive=self.thread.is_alive(),
        )
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        shutdown_thread = threading.Thread(
            target=self.server.shutdown,
            daemon=True,
            name="phase1h-shutdown",
        )
        shutdown_thread.start()
        self._phase1h_log(
            "shutdown_thread_started",
            thread_name=shutdown_thread.name,
            thread_ident=shutdown_thread.ident,
            daemon=shutdown_thread.daemon,
        )
        shutdown_thread.join(timeout=3)
        self._phase1h_log(
            "shutdown_thread_join",
            alive=shutdown_thread.is_alive(),
        )
        self.assertFalse(
            shutdown_thread.is_alive(),
            "HTTP server shutdown did not complete within 3 seconds",
        )
        self.server.server_close()
        self._phase1h_log(
            "server_thread_join_begin",
            thread_name=self.thread.name,
            thread_ident=self.thread.ident,
            alive=self.thread.is_alive(),
        )
        self.thread.join(timeout=2)
        self._phase1h_log(
            "server_thread_join",
            alive=self.thread.is_alive(),
        )
        if self._phase1h_failed:
            self._phase1h_write_artifact()
        self._phase1h_restore_handler_base()
        self._phase1h_restore_client()

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
        request = Request(
            self.base + "/v1/query",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            self._phase1h_request_scope(1)
            self._phase1h_log("client_request_begin", request_number=1, authorization="absent")
            with self.assertRaises(HTTPError) as raised:
                self._opener.open(request, timeout=3)
            self._phase1h_log(
                "client_expected_http_error",
                request_number=1,
                status=raised.exception.code,
            )
            raised.exception.close()

            request.add_header("Authorization", "Bearer " + "t" * 32)
            self._phase1h_request_scope(2)
            self._phase1h_log("client_request_begin", request_number=2, authorization="bearer")
            with self._opener.open(request, timeout=3) as response:
                payload = json.loads(response.read())
                self._phase1h_log(
                    "client_request_complete",
                    request_number=2,
                    status=response.status,
                )
                self.assertEqual("evidencia", payload["answer"])
                self.assertTrue(payload["searched"])
        except BaseException as error:
            self._phase1h_capture_failure(error)
            raise

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
