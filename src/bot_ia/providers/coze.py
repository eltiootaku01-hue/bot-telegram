# -*- coding: utf-8 -*-
"""Adaptador de Coze Open API v3.

Coze no es un endpoint de modelos OpenAI-compatible: inicia un chat y luego
expone los mensajes generados en un endpoint separado. Por eso vive como
adaptador independiente aunque participe en el mismo ProviderManager.
"""

from __future__ import annotations

import json
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bot_ia.config import SecretLoader

from .adapters import BaseProvider, HttpTransport
from .errors import (
    MissingApiKeyError,
    ProviderProtocolError,
    ProviderRateLimitError,
    ProviderRemoteError,
    ProviderTimeoutError,
)
from .models import ProviderRequest, ProviderResponse, ProviderStatus, ProviderUsage


class CozeProvider(BaseProvider):
    """Provider para bots/agentes publicados mediante Coze Open API v3."""

    provider_id = "coze"

    def __init__(
        self,
        *,
        bot_id_env: str = "COZE_BOT_ID",
        **kwargs: object,
    ) -> None:
        if kwargs.get("api_key_env") is None:
            kwargs["api_key_env"] = "COZE_API_TOKEN"
        if not kwargs.get("base_url"):
            kwargs["base_url"] = "https://api.coze.com"
        super().__init__(**kwargs)
        self.bot_id_env = bot_id_env
        self._secret_loader = SecretLoader()

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if not self.enabled:
            from .errors import ProviderDisabledError
            raise ProviderDisabledError("provider account is disabled")
        if threading.current_thread() is threading.main_thread():
            raise ProviderRemoteError(
                "CozeProvider.generate must run outside the Python main thread"
            )

        if request.provider != self.provider_id:
            raise ProviderProtocolError("request targets another provider")
        if request.account_id is not None and request.account_id != self.account_id:
            raise ProviderProtocolError("request targets another provider account")
        if len(request.input_text) > self.max_input_chars:
            from .errors import InputTooLargeError
            raise InputTooLargeError("prepared input exceeds provider limit")

        token = self._key_loader(self.api_key_env) if self.api_key_env else None
        if not token:
            raise MissingApiKeyError("Coze API token is unavailable")
        bot_id = self._secret_loader.get(self.bot_id_env)
        if not bot_id:
            raise ProviderProtocolError(f"required Coze bot id is unavailable: {self.bot_id_env}")

        start = time.monotonic()
        deadline = start + max(1.0, request.timeout_seconds)
        remaining = max(0.1, deadline - time.monotonic())
        chat = self._start_chat(token, bot_id, request, timeout_seconds=remaining)
        remaining = max(0.1, deadline - time.monotonic())
        text, usage = self._wait_for_answer(token, chat, remaining)
        return ProviderResponse(
            provider=self.provider_id,
            model=request.model,
            status=ProviderStatus.SUCCESS,
            output_text=text,
            usage=usage,
            latency_ms=int((time.monotonic() - start) * 1000),
            request_id=request.request_id,
            account_id=self.account_id,
        )

    def _start_chat(
        self,
        token: str,
        bot_id: str,
        request: ProviderRequest,
        *,
        timeout_seconds: float,
    ) -> dict[str, object]:
        payload = {
            "bot_id": bot_id,
            "user_id": request.request_id[:128],
            "stream": False,
            "auto_save_history": True,
            "additional_messages": [
                {
                    "role": "user",
                    "content": request.input_text,
                    "content_type": "text",
                }
            ],
        }
        raw = self._request_json(
            f"{self.base_url}/v3/chat",
            token,
            payload=payload,
            timeout=timeout_seconds,
        )
        if not isinstance(raw.get("data"), dict):
            raise ProviderProtocolError("Coze chat response has no data object")
        data = raw["data"]
        if not isinstance(data.get("conversation_id"), str) or not isinstance(data.get("id"), str):
            raise ProviderProtocolError("Coze chat response has no conversation/chat id")
        return data

    def _wait_for_answer(
        self,
        token: str,
        chat: dict[str, object],
        timeout_seconds: float,
    ) -> tuple[str, ProviderUsage]:
        conversation_id = str(chat["conversation_id"])
        chat_id = str(chat["id"])
        deadline = time.monotonic() + max(1.0, timeout_seconds)
        poll_waiter = threading.Event()

        while time.monotonic() < deadline:
            query = urlencode({"conversation_id": conversation_id, "chat_id": chat_id})
            raw = self._request_json(
                f"{self.base_url}/v3/chat/message/list?{query}",
                token,
                timeout=min(10.0, max(1.0, deadline - time.monotonic())),
            )
            messages = raw.get("data")
            if isinstance(messages, list):
                answers: list[str] = []
                usage = ProviderUsage()
                for message in messages:
                    if not isinstance(message, dict):
                        continue
                    if message.get("type") != "answer" or message.get("role") != "assistant":
                        continue
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        answers.append(content.strip())
                if answers:
                    return "\n\n".join(dict.fromkeys(answers)), usage
            poll_waiter.wait(0.25)

        raise ProviderTimeoutError("Coze chat did not produce an answer before timeout")

    @staticmethod
    def _request_json(
        url: str,
        token: str,
        *,
        payload: dict[str, object] | None = None,
        timeout: float,
    ) -> dict[str, object]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except TimeoutError as error:
            raise ProviderTimeoutError("Coze request timed out") from error
        except HTTPError as error:
            if error.code == 401 or error.code == 403:
                raise MissingApiKeyError("Coze authentication failed") from error
            if error.code == 429:
                raise ProviderRateLimitError("Coze rate limit reached") from error
            raise ProviderRemoteError(f"Coze returned HTTP {error.code}") from error
        except URLError as error:
            raise ProviderRemoteError("Coze connection failed") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProviderProtocolError("Coze returned invalid JSON") from error

        if not isinstance(raw, dict):
            raise ProviderProtocolError("Coze response is not a JSON object")
        if raw.get("code", 0) not in (0, "0", None):
            raise ProviderRemoteError("Coze API returned an application error")
        return raw
