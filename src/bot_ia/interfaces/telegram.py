"""Capa fina de Telegram: adapta actualizaciones a BotApplication y viceversa."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bot_ia.core.application import ApplicationRequest, ApplicationResponse, BotApplication


class TelegramInputError(ValueError):
    pass


class TelegramConfigurationError(RuntimeError):
    pass


class TelegramTransportError(RuntimeError):
    pass


class TelegramHttpError(TelegramTransportError):
    pass


class TelegramApiError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TelegramInbound:
    user_id: str
    conversation_id: str
    text: str


@dataclass(frozen=True, slots=True)
class TelegramOutbound:
    chat_id: str
    text: str
    route: str | None = None

    def payload(self) -> dict[str, str]:
        return {"chat_id": self.chat_id, "text": self.text}


def parse_update(update: dict[str, object]) -> TelegramInbound:
    try:
        message = update["message"]
        sender = message["from"]
        chat = message["chat"]
        text = message["text"]
        user_id, chat_id = str(sender["id"]), str(chat["id"])
    except (KeyError, TypeError) as error:
        raise TelegramInputError("update must contain message text, sender and chat") from error
    if not isinstance(text, str) or not text.strip():
        raise TelegramInputError("message text cannot be empty")
    return TelegramInbound(user_id, chat_id, text.strip())


class TelegramAdapter:
    def __init__(self, application: BotApplication) -> None:
        self._application = application

    def handle_update(self, update: dict[str, object]) -> TelegramOutbound:
        inbound = parse_update(update)
        command = inbound.text.casefold().split()[0]
        if command == "/start":
            return TelegramOutbound(inbound.conversation_id, "BOT-IA listo. Usa /help para ver la ayuda.", "local")
        if command == "/help":
            return TelegramOutbound(inbound.conversation_id, "Envía una consulta, una petición creativa o un cambio de universo.", "local")
        response = self._application.handle(ApplicationRequest(inbound.user_id, inbound.conversation_id, inbound.text))
        return self.from_response(inbound.conversation_id, response)

    @staticmethod
    def from_response(chat_id: str, response: ApplicationResponse) -> TelegramOutbound:
        return TelegramOutbound(chat_id, response.text, response.decision.route.value)


TelegramTransport = Callable[[str, dict[str, object], float], dict[str, object]]


def _http_post(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        status = error.code
        error.close()
        raise TelegramHttpError(f"Telegram HTTP status {status}") from error
    except (TimeoutError, URLError, OSError) as error:
        raise TelegramTransportError("Telegram transport failed") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TelegramTransportError("Telegram returned an invalid response") from error
    if not isinstance(decoded, dict):
        raise TelegramTransportError("Telegram returned an invalid response")
    return decoded


def _split_message(text: str, limit: int = 4096) -> tuple[str, ...]:
    if not text:
        raise TelegramInputError("Telegram text cannot be empty")
    if limit < 1:
        raise ValueError("message limit must be positive")
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit + 1)
        if cut < limit // 2:
            cut = remaining.rfind(" ", 0, limit + 1)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        chunks.append(remaining)
    return tuple(chunks)


class TelegramApiClient:
    def __init__(self, token: str, *, transport: TelegramTransport | None = None, timeout_seconds: float = 15.0, max_retries: int = 2, retry_delay_seconds: float = 1.0, sleeper: Callable[[float], None] = time.sleep) -> None:
        if not token:
            raise TelegramConfigurationError("Telegram token is required")
        if timeout_seconds <= 0 or max_retries < 0 or retry_delay_seconds < 0:
            raise TelegramConfigurationError("Telegram retry configuration is invalid")
        self._token, self._transport, self._timeout = token, transport or _http_post, timeout_seconds
        self._max_retries, self._retry_delay, self._sleeper = max_retries, retry_delay_seconds, sleeper

    @classmethod
    def from_environment(cls) -> "TelegramApiClient":
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise TelegramConfigurationError("TELEGRAM_BOT_TOKEN is not configured")
        return cls(token)

    def send(self, outbound: TelegramOutbound) -> dict[str, object]:
        chunks = _split_message(outbound.text)
        result: dict[str, object] | None = None
        for chunk in chunks:
            result = self._call("sendMessage", {"chat_id": outbound.chat_id, "text": chunk})
        return result or {"ok": True}

    def get_updates(self, *, offset: int | None = None, timeout_seconds: int = 25) -> tuple[dict[str, object], ...]:
        if offset is not None and offset < 0:
            raise TelegramInputError("Telegram offset cannot be negative")
        if timeout_seconds < 0 or timeout_seconds > 50:
            raise TelegramInputError("Telegram polling timeout must be between 0 and 50 seconds")
        payload: dict[str, object] = {"timeout": timeout_seconds}
        if offset is not None:
            payload["offset"] = offset
        response = self._call("getUpdates", payload, timeout_seconds=max(self._timeout, timeout_seconds + 5))
        updates = response.get("result")
        if not isinstance(updates, list) or not all(isinstance(update, dict) for update in updates):
            raise TelegramApiError("Telegram getUpdates response is invalid")
        return tuple(updates)

    def smoke_test(self) -> bool:
        response = self._call("getMe", {})
        return response.get("ok") is True

    def _call(self, method: str, payload: dict[str, object], *, timeout_seconds: float | None = None) -> dict[str, object]:
        timeout = self._timeout if timeout_seconds is None else timeout_seconds
        for attempt in range(self._max_retries + 1):
            try:
                response = self._transport(f"https://api.telegram.org/bot{self._token}/{method}", payload, timeout)
            except (TelegramTransportError, TimeoutError, OSError) as error:
                if attempt >= self._max_retries:
                    raise TelegramTransportError("Telegram transport failed after controlled retries") from error
                self._sleeper(self._retry_delay)
                continue
            if not isinstance(response, dict) or response.get("ok") is not True:
                raise TelegramApiError("Telegram API returned an error")
            return response
        raise AssertionError("unreachable")


@dataclass(frozen=True, slots=True)
class PollingConfig:
    poll_timeout_seconds: int = 25
    idle_delay_seconds: float = 1.0
    retry_delay_seconds: float = 2.0
    max_consecutive_failures: int = 3

    def __post_init__(self) -> None:
        if not 0 <= self.poll_timeout_seconds <= 50 or self.idle_delay_seconds < 0 or self.retry_delay_seconds < 0 or self.max_consecutive_failures < 1:
            raise ValueError("invalid Telegram polling configuration")


@dataclass(frozen=True, slots=True)
class PollingResult:
    polls: int
    updates_received: int
    updates_processed: int
    updates_skipped: int
    responses_sent: int
    transport_errors: int
    stopped: bool


class TelegramPoller:
    def __init__(self, client: TelegramApiClient, adapter: TelegramAdapter, *, config: PollingConfig | None = None, sleeper: Callable[[float], None] = time.sleep, logger: Callable[[str], None] | None = None) -> None:
        self._client, self._adapter, self._config = client, adapter, config or PollingConfig()
        self._sleeper, self._logger, self._running, self._offset = sleeper, logger or (lambda _: None), True, None

    @property
    def offset(self) -> int | None:
        return self._offset

    def stop(self) -> None:
        self._running = False

    def run(self, *, max_cycles: int | None = None) -> PollingResult:
        if max_cycles is not None and max_cycles < 0:
            raise ValueError("max_cycles cannot be negative")
        polls = received = processed = skipped = sent = errors = cycles = consecutive_failures = 0
        while self._running and (max_cycles is None or cycles < max_cycles):
            cycles += 1
            try:
                updates = self._client.get_updates(offset=self._offset, timeout_seconds=self._config.poll_timeout_seconds)
            except TelegramTransportError:
                errors += 1
                consecutive_failures += 1
                self._logger("telegram polling transport error")
                if consecutive_failures >= self._config.max_consecutive_failures:
                    self.stop()
                    break
                self._sleeper(self._config.retry_delay_seconds)
                continue
            polls += 1
            consecutive_failures = 0
            received += len(updates)
            for update in updates:
                update_id = update.get("update_id")
                if not isinstance(update_id, int) or (self._offset is not None and update_id < self._offset):
                    skipped += 1
                    self._logger("telegram update skipped")
                    continue
                try:
                    outbound = self._adapter.handle_update(update)
                except TelegramInputError:
                    # Poisoned/unsupported updates are acknowledged so they do not
                    # block the queue forever.
                    self._offset = update_id + 1
                    skipped += 1
                    self._logger("telegram update rejected")
                    continue
                try:
                    self._client.send(outbound)
                except (TelegramTransportError, TelegramApiError, TelegramInputError):
                    # Do not advance the offset until delivery succeeds; Telegram
                    # can redeliver the update after a transient failure.
                    self._logger("telegram response delivery failed")
                    continue
                self._offset = update_id + 1
                processed += 1
                sent += 1
            if self._running and not updates:
                self._sleeper(self._config.idle_delay_seconds)
        return PollingResult(polls, received, processed, skipped, sent, errors, not self._running)
