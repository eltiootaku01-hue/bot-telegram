"""HTTP interface for local use and ChatGPT GPT Actions."""

from __future__ import annotations

import hmac
import ipaddress
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from bot_ia.core.application import ApplicationRequest, BotApplication


MAX_MESSAGE_CHARS = 24_000
MAX_ID_CHARS = 128


class WebApiError(ValueError):
    """Invalid request sent to the BOT-IA HTTP API."""


class ExternalApiAuthorizationError(PermissionError):
    """The HTTP surface is not configured to authorize external API use."""


class WebApi:
    """Small dependency-free JSON API around :class:`BotApplication`."""

    def __init__(
        self,
        application: BotApplication,
        *,
        api_token: str | None = None,
        allow_external_api: bool = False,
    ) -> None:
        self._application = application
        self._api_token = api_token
        self._allow_external_api = allow_external_api

    def authorize(self, authorization: str | None) -> bool:
        if self._api_token is None:
            return True
        expected = f"Bearer {self._api_token}".encode("utf-8")
        supplied = (authorization or "").encode("utf-8")
        return hmac.compare_digest(supplied, expected)

    def query(self, payload: object) -> dict[str, object]:
        if not isinstance(payload, dict):
            raise WebApiError("JSON body must be an object")
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            raise WebApiError("message is required")
        message = message.strip()
        if len(message) > MAX_MESSAGE_CHARS:
            raise WebApiError(f"message exceeds {MAX_MESSAGE_CHARS} characters")

        user_id = payload.get("user_id", "web-user")
        conversation_id = payload.get("conversation_id", "web-session")
        allow_external_api = payload.get("allow_external_api", False)
        if not isinstance(user_id, str) or not user_id.strip():
            raise WebApiError("user_id must be a non-empty string")
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise WebApiError("conversation_id must be a non-empty string")
        user_id = user_id.strip()
        conversation_id = conversation_id.strip()
        if len(user_id) > MAX_ID_CHARS:
            raise WebApiError(f"user_id exceeds {MAX_ID_CHARS} characters")
        if len(conversation_id) > MAX_ID_CHARS:
            raise WebApiError(f"conversation_id exceeds {MAX_ID_CHARS} characters")
        if not isinstance(allow_external_api, bool):
            raise WebApiError("allow_external_api must be a boolean")
        if allow_external_api and not self._allow_external_api:
            raise ExternalApiAuthorizationError("external API authorization is disabled for this HTTP surface")

        response = self._application.handle(
            ApplicationRequest(
                user_id,
                conversation_id,
                message,
                allow_external_api=allow_external_api,
            )
        )
        execution = response.execution
        provider_response = getattr(execution, "provider_response", None)
        provider = getattr(provider_response, "provider", None)
        return {
            "answer": response.text,
            "route": response.decision.route.value,
            "universe_id": response.brain.universe_id,
            "agent_id": response.decision.agent_id,
            "searched": bool(getattr(execution, "searched", False)),
            "provider": provider,
            "external_api_authorized": bool(getattr(response.decision, "external_api_authorized", False)),
        }


def openapi_document(base_url: str, *, allow_external_api: bool = False) -> dict[str, object]:
    """Return the OpenAPI document used by ChatGPT GPT Actions."""
    description = "False keeps BOT-IA local-only."
    if not allow_external_api:
        description += " The HTTP surface is not configured to authorize external API use."
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "BOT-IA Knowledge Engine",
            "version": "1.0.0",
            "description": "Personal knowledge engine with evidence-gated answers.",
        },
        "servers": [{"url": base_url.rstrip("/")}],
        "paths": {
            "/health": {
                "get": {
                    "operationId": "health",
                    "summary": "Check BOT-IA availability",
                    "responses": {"200": {"description": "Service is available."}},
                }
            },
            "/v1/query": {
                "post": {
                    "operationId": "queryBotIA",
                    "summary": "Ask BOT-IA",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/QueryRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "BOT-IA response.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/QueryResponse"}}},
                        },
                        "400": {"description": "Invalid request."},
                        "401": {"description": "Authentication required."},
                        "403": {"description": "External API authorization is disabled."},
                        "500": {"description": "Internal server error."},
                    },
                    "security": [{"bearerAuth": []}],
                }
            },
        },
        "components": {
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}},
            "schemas": {
                "QueryRequest": {
                    "type": "object",
                    "required": ["message"],
                    "properties": {
                        "message": {"type": "string", "maxLength": MAX_MESSAGE_CHARS, "description": "User request."},
                        "user_id": {"type": "string", "maxLength": MAX_ID_CHARS, "default": "chatgpt-user"},
                        "conversation_id": {"type": "string", "maxLength": MAX_ID_CHARS, "default": "chatgpt-session"},
                        "allow_external_api": {"type": "boolean", "default": False, "description": description},
                    },
                },
                "QueryResponse": {
                    "type": "object",
                    "required": ["answer", "route", "searched"],
                    "properties": {
                        "answer": {"type": "string"},
                        "route": {"type": "string"},
                        "universe_id": {"type": ["string", "null"]},
                        "agent_id": {"type": ["string", "null"]},
                        "searched": {"type": "boolean"},
                        "provider": {"type": ["string", "null"]},
                        "external_api_authorized": {"type": "boolean"},
                    },
                },
            },
        },
    }


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def create_web_server(
    api: WebApi,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    public_base_url: str | None = None,
) -> ThreadingHTTPServer:
    if not _is_loopback_host(host) and not api._api_token:
        raise WebApiError("non-loopback HTTP binding requires an API token")
    base_url = public_base_url or f"http://{host}:{port}"

    class Handler(BaseHTTPRequestHandler):
        server_version = "BOT-IA/1.0"

        def _send(self, status: int, payload: object, *, content_type: str = "application/json") -> None:
            body = _json_bytes(payload) if content_type == "application/json" else payload
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._send(HTTPStatus.NO_CONTENT, b"", content_type="text/plain")

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send(HTTPStatus.OK, {"ok": True, "service": "bot-ia"})
                return
            if self.path == "/openapi.json":
                self._send(HTTPStatus.OK, openapi_document(base_url, allow_external_api=api._allow_external_api))
                return
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/query":
                self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            if not api.authorize(self.headers.get("Authorization")):
                self._send(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length <= 0 or content_length > 1_000_000:
                    raise WebApiError("request body size is invalid")
                raw = self.rfile.read(content_length)
                payload = json.loads(raw.decode("utf-8"))
                result = api.query(payload)
            except ExternalApiAuthorizationError as error:
                self._send(HTTPStatus.FORBIDDEN, {"error": str(error)})
                return
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError, WebApiError) as error:
                self._send(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            except Exception:
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error"})
                return
            self._send(HTTPStatus.OK, result)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


def run_web_server(
    application: BotApplication,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    api_token: str | None = None,
    allow_external_api: bool = False,
    public_base_url: str | None = None,
) -> None:
    server = create_web_server(
        WebApi(application, api_token=api_token, allow_external_api=allow_external_api),
        host=host,
        port=port,
        public_base_url=public_base_url,
    )
    print(f"BOT-IA API escuchando en http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
