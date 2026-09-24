# -*- coding: utf-8 -*-
"""Capa de Telegram: conversación natural + menús contextuales sin hoja de comandos."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bot_ia.core.application import ApplicationRequest, ApplicationResponse, BotApplication
from bot_ia.librarian.models import CoverageStatus


class TelegramInputError(ValueError):
    pass


MAX_INBOUND_TEXT_CHARS = 24_000
MAX_CALLBACK_DATA_CHARS = 256


class TelegramConfigurationError(RuntimeError):
    pass


class TelegramTransportError(RuntimeError):
    pass


class TelegramHttpError(TelegramTransportError):
    pass


class TelegramApiError(RuntimeError):
    pass


class TelegramPartialDeliveryError(TelegramTransportError):
    def __init__(self, next_chunk_index: int) -> None:
        super().__init__("Telegram delivery failed after a partial message")
        self.next_chunk_index = next_chunk_index


@dataclass(frozen=True, slots=True)
class TelegramInbound:
    user_id: str
    conversation_id: str
    text: str


@dataclass(frozen=True, slots=True)
class TelegramCallback:
    user_id: str
    conversation_id: str
    data: str


@dataclass(frozen=True, slots=True)
class TelegramOutbound:
    chat_id: str
    text: str
    route: str | None = None
    keyboard: tuple[tuple[tuple[str, str], ...], ...] = ()

    def payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"chat_id": self.chat_id, "text": self.text}
        if self.keyboard:
            payload["reply_markup"] = {"inline_keyboard": [[{"text": label, "callback_data": data} for label, data in row] for row in self._normalized_keyboard()]}
        return payload

    def _normalized_keyboard(self) -> tuple[tuple[tuple[str, str], ...], ...]:
        """Normaliza filas antiguas de dos botones sin romper el contrato nuevo."""
        normalized: list[tuple[tuple[str, str], ...]] = []
        for row in self.keyboard:
            if isinstance(row, tuple) and len(row) == 2 and all(isinstance(value, str) for value in row):
                normalized.append((row,))
                continue
            if not isinstance(row, (tuple, list)):
                raise TelegramInputError("keyboard row must be a button pair or row of button pairs")
            buttons: list[tuple[str, str]] = []
            for button in row:
                if not isinstance(button, (tuple, list)) or len(button) != 2:
                    raise TelegramInputError("keyboard button must contain label and callback_data")
                label, data = button
                if not isinstance(label, str) or not isinstance(data, str):
                    raise TelegramInputError("keyboard label and callback_data must be strings")
                buttons.append((label, data))
            normalized.append(tuple(buttons))
        return tuple(normalized)


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
    text = text.strip()
    if len(text) > MAX_INBOUND_TEXT_CHARS:
        raise TelegramInputError("message text is too long")
    return TelegramInbound(user_id, chat_id, text)


def parse_callback_update(update: dict[str, object]) -> TelegramCallback:
    try:
        callback = update["callback_query"]
        sender = callback["from"]
        message = callback["message"]
        chat = message["chat"]
        data = callback["data"]
        user_id, chat_id = str(sender["id"]), str(chat["id"])
    except (KeyError, TypeError) as error:
        raise TelegramInputError("callback update is invalid") from error
    if not isinstance(data, str) or not data.strip():
        raise TelegramInputError("callback data cannot be empty")
    data = data.strip()
    if len(data) > MAX_CALLBACK_DATA_CHARS:
        raise TelegramInputError("callback data is too long")
    return TelegramCallback(user_id, chat_id, data)


class TelegramAdapter:
    """Presenta una interfaz visual pequeña; la aplicación sigue siendo agnóstica de Telegram."""

    MAIN_MENU = (
        (("✍️ Escribir novela", "menu:write"), ("📝 Editar texto", "menu:edit")),
        (("📚 Biblioteca", "menu:library"), ("🧭 Continuidad", "menu:continuity")),
        (("💡 Ideas", "menu:ideas"), ("❓ Ayuda", "menu:help")),
    )

    def __init__(self, application: BotApplication) -> None:
        self._application = application

    def handle_update(self, update: dict[str, object]) -> TelegramOutbound:
        if "callback_query" in update:
            return self.handle_callback(update)
        inbound = parse_update(update)
        command = inbound.text.casefold().split()[0]
        if command in {"/start", "/menu"}:
            return TelegramOutbound(inbound.conversation_id, "¡listo! ¿Qué quieres hacer?", "local", self.MAIN_MENU)
        if command == "/help":
            return TelegramOutbound(inbound.conversation_id, "Envía lo que necesitas o usa el menú. Puedes escribir, editar, consultar la biblioteca, revisar continuidad o generar ideas.", "local", self.MAIN_MENU)
        response = self._application.handle(ApplicationRequest(inbound.user_id, inbound.conversation_id, inbound.text))
        return self.from_response(inbound.conversation_id, response)

    def handle_callback(self, update: dict[str, object]) -> TelegramOutbound:
        callback = parse_callback_update(update)
        actions = {
            "menu:write": "Quiero escribir una escena o capítulo. Ayúdame usando los archivos locales del proyecto y la continuidad establecida.",
            "menu:edit": "Quiero editar o revisar un texto usando los archivos locales relevantes como referencia.",
            "menu:library": "¿Qué información y documentos tengo disponibles en la biblioteca local?",
            "menu:continuity": "Quiero revisar la continuidad de lo que estamos escribiendo y saber dónde quedamos.",
            "menu:ideas": "Quiero ideas para continuar la novela usando la continuidad y personajes establecidos.",
        }
        if callback.data == "menu:help":
            return TelegramOutbound(callback.conversation_id, "Escribe lo que necesitas; BOT-IA decide si basta la información local, si necesita consultar archivos o si conviene pedir autorización antes de usar una API.", "local", self.MAIN_MENU)
        if callback.data == "menu:main":
            return TelegramOutbound(callback.conversation_id, "Menú principal:", "local", self.MAIN_MENU)
        if callback.data == "fallback:prompt":
            return TelegramOutbound(callback.conversation_id, "Puedo preparar un prompt para pegar en otra IA web sin enviar tu consulta a ninguna API desde BOT-IA.", "local", (("📋 Generar prompt", "prompt:generate"), ("⬅️ Menú", "menu:main")))
        if callback.data == "fallback:api":
            return TelegramOutbound(callback.conversation_id, "Autorización recibida para esta consulta. BOT-IA puede usar la API configurada sólo para esta petición.", "local", (("⬅️ Menú", "menu:main"),))
        if callback.data == "prompt:generate":
            return TelegramOutbound(callback.conversation_id, "Para generar el prompt exacto necesito que me envíes nuevamente la pregunta que quieres investigar. No se enviará a ninguna API desde este botón.", "local", (("⬅️ Menú", "menu:main"),))
        text = actions.get(callback.data)
        if text is None:
            raise TelegramInputError("unknown Telegram callback")
        response = self._application.handle(ApplicationRequest(callback.user_id, callback.conversation_id, text))
        return self.from_response(callback.conversation_id, response)

    @staticmethod
    def from_response(chat_id: str, response: ApplicationResponse) -> TelegramOutbound:
        keyboard: tuple[tuple[tuple[str, str], ...], ...] = ()
        execution = response.execution
        evidence = getattr(execution, "evidence", None)
        if evidence is not None and getattr(evidence.coverage, "status", None) in {CoverageStatus.NO_ENCONTRADO, CoverageStatus.NO_ESTABLECIDO}:
            keyboard = ((("🔐 Usar API para esta consulta", "fallback:api"),), (("📋 Preparar prompt para otra IA", "fallback:prompt"),), (("⬅️ Menú", "menu:main"),))
        return TelegramOutbound(chat_id, response.text, response.decision.route.value, keyboard)


TelegramTransport = Callable[[str, dict[str, object], float], dict[str, object]]


def _http_post(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        status = error.code
        error.close()
        if status in {401, 403}:
            raise TelegramApiError("Telegram authentication or authorization failed") from error
        if status == 429 or status >= 500:
            raise TelegramHttpError(f"Telegram HTTP status {status}") from error
        raise TelegramApiError(f"Telegram HTTP status {status}") from error
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

    def send(self, outbound: TelegramOutbound, *, start_chunk: int = 0) -> dict[str, object]:
        chunks = _split_message(outbound.text)
        if start_chunk < 0 or start_chunk > len(chunks):
            raise TelegramInputError("invalid Telegram chunk index")
        result: dict[str, object] | None = None
        for index in range(start_chunk, len(chunks)):
            chunk = chunks[index]
            payload = outbound.payload()
            payload["text"] = chunk
            if index < len(chunks) - 1:
                payload.pop("reply_markup", None)
            try:
                result = self._call("sendMessage", payload)
            except TelegramTransportError as error:
                raise TelegramPartialDeliveryError(index) from error
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
        self._pending_delivery: tuple[int, TelegramOutbound, int] | None = None

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

            if self._pending_delivery is not None:
                pending_id, pending_outbound, next_chunk = self._pending_delivery
                try:
                    self._client.send(pending_outbound, start_chunk=next_chunk)
                except TelegramPartialDeliveryError as error:
                    errors += 1
                    self._pending_delivery = (pending_id, pending_outbound, error.next_chunk_index)
                    self._logger("telegram pending response delivery failed after partial send")
                    self._sleeper(self._config.retry_delay_seconds)
                    continue
                except TelegramTransportError:
                    errors += 1
                    self._logger("telegram pending response delivery failed")
                    self._sleeper(self._config.retry_delay_seconds)
                    continue
                except (TelegramApiError, TelegramInputError):
                    self._pending_delivery = None
                    self._offset = pending_id + 1
                    skipped += 1
                    self._logger("telegram pending response rejected")
                    continue
                self._pending_delivery = None
                self._offset = pending_id + 1
                processed += 1
                sent += 1
                continue

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
                    self._offset = update_id + 1
                    skipped += 1
                    self._logger("telegram update rejected")
                    continue
                except Exception as error:
                    self._offset = update_id + 1
                    skipped += 1
                    self._logger(f"telegram update processing failed: {type(error).__name__}")
                    continue
                try:
                    self._client.send(outbound)
                except TelegramPartialDeliveryError as error:
                    self._pending_delivery = (update_id, outbound, error.next_chunk_index)
                    self._logger("telegram response delivery deferred after partial send")
                    break
                except TelegramTransportError:
                    self._pending_delivery = (update_id, outbound, 0)
                    self._logger("telegram response delivery deferred for retry")
                    break
                except (TelegramApiError, TelegramInputError):
                    self._offset = update_id + 1
                    skipped += 1
                    self._logger("telegram response delivery rejected")
                    continue
                self._offset = update_id + 1
                processed += 1
                sent += 1
            if self._running and not updates:
                self._sleeper(self._config.idle_delay_seconds)
        return PollingResult(polls, received, processed, skipped, sent, errors, not self._running)
