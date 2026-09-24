# -*- coding: utf-8 -*-
"""Adaptadores HTTP de proveedores de modelos."""

from __future__ import annotations

import json
import socket
import time

from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bot_ia.config import SecretLoader

from .errors import (
    InputTooLargeError,
    MissingApiKeyError,
    ProviderDisabledError,
    ProviderProtocolError,
    ProviderRateLimitError,
    ProviderRemoteError,
    ProviderTimeoutError,
)

from .models import (
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderUsage,
    ProviderHealth,
)


MAX_PROVIDER_HTTP_RESPONSE_BYTES = 4 * 1024 * 1024


HttpTransport = Callable[
    [str, dict[str, str], dict[str, object], float],
    dict[str, object],
]


def _stdlib_transport(
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    timeout: float,
) -> dict[str, object]:

    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw_body = response.read(MAX_PROVIDER_HTTP_RESPONSE_BYTES + 1)
            if len(raw_body) > MAX_PROVIDER_HTTP_RESPONSE_BYTES:
                raise ProviderProtocolError(
                    "provider response body exceeds safety limit"
                )
            body = raw_body.decode("utf-8")
            return json.loads(body)

    except socket.timeout as error:
        raise ProviderTimeoutError(
            "provider request timed out"
        ) from error

    except HTTPError as error:
        try:
            if error.code == 401:
                raise MissingApiKeyError(
                    "provider authentication failed"
                ) from error

            if error.code == 429:
                raise ProviderRateLimitError(
                    "provider rate limit reached"
                ) from error

            if 400 <= error.code < 500:
                raise ProviderRemoteError(
                    f"provider returned HTTP {error.code}"
                ) from error

            raise ProviderRemoteError(
                f"provider returned HTTP {error.code}"
            ) from error
        finally:
            error.close()

    except URLError as error:
        raise ProviderRemoteError(
            "provider connection failed"
        ) from error

    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderProtocolError(
            "provider returned invalid JSON"
        ) from error


class BaseProvider:

    provider_id = ""

    def __init__(
        self,
        *,
        account_id: str | None = None,
        api_key_env: str | None = None,
        base_url: str = "",
        enabled: bool = True,
        default_model: str | None = None,
        default_max_output_tokens: int = 128,
        default_timeout_seconds: float = 30.0,
        cooldown_seconds: float = 60.0,
        max_input_chars: int = 24_000,
        key_loader: Callable[[str], str | None] | None = None,
        transport: HttpTransport | None = None,
    ) -> None:

        self.account_id = account_id or self.provider_id
        self.api_key_env = api_key_env
        self.base_url = base_url.rstrip("/")
        self.enabled = enabled
        self.default_model = default_model
        self.default_max_output_tokens = default_max_output_tokens
        self.default_timeout_seconds = default_timeout_seconds
        self.cooldown_seconds = cooldown_seconds
        self.max_input_chars = max_input_chars

        self._key_loader = (
            key_loader or SecretLoader().get
        )

        self._transport = (
            transport or _stdlib_transport
        )

    def generate(
        self,
        request: ProviderRequest,
    ) -> ProviderResponse:

        if not self.enabled:
            raise ProviderDisabledError(
                "provider account is disabled"
            )

        if request.provider != self.provider_id:
            raise ProviderProtocolError(
                "request targets another provider"
            )

        if (
            request.account_id is not None
            and request.account_id != self.account_id
        ):
            raise ProviderProtocolError(
                "request targets another provider account"
            )

        if len(request.input_text) > self.max_input_chars:
            raise InputTooLargeError(
                "prepared input exceeds provider limit"
            )

        key = None

        if self.api_key_env:
            key = self._key_loader(
                self.api_key_env
            )

            if not key:
                raise MissingApiKeyError(
                    "provider key is unavailable"
                )

        start = time.monotonic()

        payload = self._payload(request)

        raw = self._transport(
            self._url(request),
            self._headers(key),
            payload,
            request.timeout_seconds,
        )

        text, usage = self._parse(raw)

        latency = int(
            (time.monotonic() - start) * 1000
        )

        return ProviderResponse(
            provider=self.provider_id,
            model=request.model,
            status=ProviderStatus.SUCCESS,
            output_text=text,
            usage=usage,
            latency_ms=latency,
            request_id=request.request_id,
            account_id=self.account_id,
            health=ProviderHealth.ACTIVE,
        )

    def _headers(
        self,
        key: str | None,
    ) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }

        if key:
            headers["Authorization"] = (
                f"Bearer {key}"
            )

        return headers

    def _url(
        self,
        request: ProviderRequest,
    ) -> str:
        raise NotImplementedError

    def _payload(
        self,
        request: ProviderRequest,
    ) -> dict[str, object]:
        raise NotImplementedError

    def _parse(
        self,
        raw: dict[str, object],
    ) -> tuple[str, ProviderUsage]:
        raise NotImplementedError


class OpenAICompatibleProvider(BaseProvider):
    """
    Provider para APIs compatibles con OpenAI.

    Sirve para:
    - OpenAI
    - Groq
    - OpenRouter
    - futuros proveedores compatibles
    """

    def _url(
        self,
        request: ProviderRequest,
    ) -> str:

        return (
            f"{self.base_url}/responses"
        )

    def _payload(
        self,
        request: ProviderRequest,
    ) -> dict[str, object]:

        return {
            "model": request.model,
            "input": request.input_text,
            "max_output_tokens": (
                request.max_output_tokens
            ),
        }

    def _parse(
        self,
        raw: dict[str, object],
    ) -> tuple[str, ProviderUsage]:

        output_text = raw.get(
            "output_text"
        )

        if isinstance(output_text, str):
            usage_raw = raw.get("usage")

            if not isinstance(
                usage_raw,
                dict,
            ):
                usage_raw = {}

            return (
                output_text,
                ProviderUsage(
                    input_tokens=usage_raw.get(
                        "input_tokens"
                    ),
                    output_tokens=usage_raw.get(
                        "output_tokens"
                    ),
                    total_tokens=usage_raw.get(
                        "total_tokens"
                    ),
                ),
            )

        # Compatibilidad adicional con respuestas
        # donde output_text no viene directamente.
        output = raw.get("output")

        if isinstance(output, list):

            texts: list[str] = []

            for item in output:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                content = item.get(
                    "content"
                )

                if not isinstance(
                    content,
                    list,
                ):
                    continue

                for content_item in content:

                    if not isinstance(
                        content_item,
                        dict,
                    ):
                        continue

                    text = content_item.get(
                        "text"
                    )

                    if isinstance(
                        text,
                        str,
                    ):
                        texts.append(text)

            if texts:

                usage_raw = raw.get(
                    "usage"
                )

                if not isinstance(
                    usage_raw,
                    dict,
                ):
                    usage_raw = {}

                return (
                    "\n".join(texts),
                    ProviderUsage(
                        input_tokens=usage_raw.get(
                            "input_tokens"
                        ),
                        output_tokens=usage_raw.get(
                            "output_tokens"
                        ),
                        total_tokens=usage_raw.get(
                            "total_tokens"
                        ),
                    ),
                )

        raise ProviderProtocolError(
            "provider response has no supported text output"
        )


class OpenAIProvider(OpenAICompatibleProvider):
    """Adaptador de la Responses API de OpenAI."""

    provider_id = "openai"

    def __init__(self, **kwargs: object) -> None:
        if kwargs.get("api_key_env") is None:
            kwargs["api_key_env"] = "OPENAI_API_KEY"
        if not kwargs.get("base_url"):
            kwargs["base_url"] = "https://api.openai.com/v1"
        super().__init__(**kwargs)

    def _payload(self, request: ProviderRequest) -> dict[str, object]:
        payload = super()._payload(request)
        payload["store"] = False
        return payload


class GeminiProvider(BaseProvider):
    """Adaptador de Gemini, incluyendo el formato de fixtures histórico."""

    provider_id = "gemini"

    def __init__(self, **kwargs: object) -> None:
        if kwargs.get("api_key_env") is None:
            kwargs["api_key_env"] = "GEMINI_API_KEY"
        if not kwargs.get("base_url"):
            kwargs["base_url"] = "https://generativelanguage.googleapis.com/v1beta"
        super().__init__(**kwargs)

    def _headers(self, key: str | None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if key:
            headers["x-goog-api-key"] = key
        return headers

    def _url(self, request: ProviderRequest) -> str:
        return f"{self.base_url}/interactions"

    def _payload(self, request: ProviderRequest) -> dict[str, object]:
        return {
            "model": request.model,
            "input": request.input_text,
            "store": False,
            "generation_config": {
                "max_output_tokens": request.max_output_tokens,
                "thinking_level": "low",
            },
        }

    def _parse(self, raw: dict[str, object]) -> tuple[str, ProviderUsage]:
        usage_raw = raw.get("usage")
        if not isinstance(usage_raw, dict):
            usage_raw = raw.get("usageMetadata")
        if not isinstance(usage_raw, dict):
            usage_raw = {}

        usage = ProviderUsage(
            usage_raw.get("total_input_tokens", usage_raw.get("promptTokenCount")),
            usage_raw.get("total_output_tokens", usage_raw.get("candidatesTokenCount")),
            usage_raw.get("total_tokens", usage_raw.get("totalTokenCount")),
        )
        steps = raw.get("steps")
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict) or step.get("type") != "model_output":
                    continue
                content = step.get("content")
                if not isinstance(content, list):
                    continue
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                        return item["text"], usage

        candidates = raw.get("candidates")
        if isinstance(candidates, list) and candidates:
            first = candidates[0]
            if isinstance(first, dict):
                content = first.get("content")
                if isinstance(content, dict):
                    parts = content.get("parts")
                    if isinstance(parts, list) and parts:
                        part = parts[0]
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            return part["text"], usage

        raise ProviderProtocolError("Gemini response has no supported text output")


class ChatCompletionsProvider(OpenAICompatibleProvider):
    """Adaptador para APIs OpenAI-compatible que exponen chat/completions."""

    def _url(self, request: ProviderRequest) -> str:
        return f"{self.base_url}/chat/completions"

    def _payload(self, request: ProviderRequest) -> dict[str, object]:
        return {
            "model": request.model,
            "messages": [{"role": "user", "content": request.input_text}],
            "max_tokens": request.max_output_tokens,
        }

    def _parse(self, raw: dict[str, object]) -> tuple[str, ProviderUsage]:
        choices = raw.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    usage_raw = raw.get("usage")
                    if not isinstance(usage_raw, dict):
                        usage_raw = {}
                    return message["content"], ProviderUsage(
                        input_tokens=usage_raw.get("prompt_tokens"),
                        output_tokens=usage_raw.get("completion_tokens"),
                        total_tokens=usage_raw.get("total_tokens"),
                    )
        return super()._parse(raw)


class GroqProvider(ChatCompletionsProvider):
    """Provider Groq usando chat/completions compatible con OpenAI."""

    provider_id = "groq"

    def __init__(self, **kwargs: object) -> None:
        if kwargs.get("api_key_env") is None:
            kwargs["api_key_env"] = "GROQ_API_KEY"
        if not kwargs.get("base_url"):
            kwargs["base_url"] = "https://api.groq.com/openai/v1"
        super().__init__(**kwargs)


class OpenRouterProvider(ChatCompletionsProvider):
    """Provider OpenRouter usando chat/completions compatible con OpenAI."""

    provider_id = "openrouter"

    def __init__(self, **kwargs: object) -> None:
        if kwargs.get("api_key_env") is None:
            kwargs["api_key_env"] = "OPENROUTER_API_KEY"
        if not kwargs.get("base_url"):
            kwargs["base_url"] = "https://openrouter.ai/api/v1"
        super().__init__(**kwargs)


class OllamaProvider(BaseProvider):

    provider_id = "ollama"

    def __init__(self, **kwargs: object) -> None:
        if not kwargs.get("base_url"):
            kwargs["base_url"] = "http://localhost:11434"
        super().__init__(**kwargs)

    def _headers(
        self,
        key: str | None,
    ) -> dict[str, str]:

        return {
            "Content-Type": "application/json"
        }

    def _url(
        self,
        request: ProviderRequest,
    ) -> str:

        return (
            f"{self.base_url}/api/generate"
        )

    def _payload(
        self,
        request: ProviderRequest,
    ) -> dict[str, object]:

        return {
            "model": request.model,
            "prompt": request.input_text,
            "stream": False,
            "think": False,
            "keep_alive": 0,
            "options": {
                "num_predict": (
                    request.max_output_tokens
                )
            },
        }

    def _parse(
        self,
        raw: dict[str, object],
    ) -> tuple[str, ProviderUsage]:

        text = raw.get("response")

        if not isinstance(
            text,
            str,
        ):
            raise ProviderProtocolError(
                "Ollama response has no response text"
            )

        input_tokens = raw.get(
            "prompt_eval_count"
        )

        output_tokens = raw.get(
            "eval_count"
        )

        input_count = (
            input_tokens
            if isinstance(input_tokens, int)
            else None
        )

        output_count = (
            output_tokens
            if isinstance(output_tokens, int)
            else None
        )

        total_count = None

        if (
            input_count is not None
            and output_count is not None
        ):
            total_count = (
                input_count
                + output_count
            )

        return (
            text,
            ProviderUsage(
                input_count,
                output_count,
                total_count,
            ),
        )
