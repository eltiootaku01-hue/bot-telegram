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
class TelegramCallback:
    user_id: str
    conversation_id: str
    data: str


@dataclass(frozen=True, slots=True)
class TelegramOutbound:
    chat_id: str
    text: str
    route: str | None = None
    keyboard: tuple = ()

    def payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"chat_id": self.chat_id, "text": self.text}
        if self.keyboard:
            rows = self._normalized_keyboard()
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": label, "callback_data": data} for label, data in row]
                    for row in rows
                ]
            }
        return payload

    def _normalized_keyboard(self) -> tuple[tuple[tuple[str, str], ...], ...]:
        """Acepta tanto el contrato anidado como el antiguo formato de una fila.

        Algunas interfaces históricas construían ``((label, data), (label, data))``
        en lugar de ``(((label, data), (label, data)),)``. Normalizar aquí evita
        romper esos menús y mantiene la serialización de Telegram determinista.
        """
        normalized: list[tuple[tuple[str, str], ...]] = []
        for row in self.keyboard:
            if (
                isinstance(row, tuple)
                and len(row) == 2
                and all(isinstance(value, str) for value in row)
            ):
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
    return TelegramInbound(user_id, chat_id, text.strip())


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
    return TelegramCallback(user_id, chat_id, data.strip())


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
            return TelegramOutbound(inbound.conversation_id, "¡Listo! ¿Qué quieres hacer?", "local", self.MAIN_MENU)
        if command == "/help":
            return TelegramOutbound(inbound.conversation_id, "Usa los botones para elegir una acción o escribe directamente lo que necesitas.", "local", self.MAIN_MENU)
        response = self._application.handle(ApplicationRequest(inbound.user_id, inbound.conversation_id, inbound.text))
        return self.from_response(inbound.conversation_id, response)

    def handle_callback(self, update: dict[str, object]) -> TelegramOutbound:
        callback = parse_callback_update(update)
        if callback.data == "menu:main":
            return TelegramOutbound(callback.conversation_id, "¡Listo! Menú principal:", "local", self.MAIN_MENU)
        return TelegramOutbound(callback.conversation_id, "Opción recibida.", "local", self.MAIN_MENU)

    def from_response(self, chat_id: str, response: ApplicationResponse) -> TelegramOutbound:
        text = response.text
        keyboard: tuple = ()
        if response.decision.route is not None:
            if response.execution is not None and getattr(response.execution, "evidence", None) is not None:
                evidence = response.execution.evidence
                if evidence.coverage.status is CoverageStatus.NO_ENCONTRADO:
                    keyboard = (
                        (("🔐 Usar API", "fallback:api"), ("📋 Preparar prompt", "fallback:prompt")),
                        (("⬅️ Menú", "menu:main"),),
                    )
        return TelegramOutbound(chat_id, text, response.decision.route.value, keyboard)


class TelegramApiClient:
    """Cliente HTTP mínimo para Bot API, con reintentos controlados."""

    def __init__(self, token: str, *, timeout: float = 30.0, retries: int = 2, sleeper: Callable[[float], None] = time.sleep) -> None:
        if not token:
            raise TelegramConfigurationError("TELEGRAM_BOT_TOKEN is required")
        self._base = f"https://api.telegram.org/bot{token}"
        self._timeout = timeout
        self._retries = retries
        self._sleeper = sleeper

    @classmethod
    def from_environment(cls) -> "TelegramApiClient":
        return cls(os.getenv("TELEGRAM_BOT_TOKEN", ""))

    def smoke_test(self) -> bool:
        response = self._request("getMe", {})
        return bool(response.get("ok"))

    def get_updates(self, offset: int | None = None, timeout: int = 20) -> tuple[dict[str, object], ...]:
        payload: dict[str, object] = {"timeout": timeout}
        if offset is not None:
            payload["offset"] = offset
        response = self._request("getUpdates", payload)
        result = response.get("result", [])
        if not isinstance(result, list):
            raise TelegramApiError("Telegram result is not a list")
        return tuple(item for item in result if isinstance(item, dict))

    def send(self, outbound: TelegramOutbound) -> dict[str, object]:
        return self._request("sendMessage", outbound.payload())

    def _request(self, method: str, payload: dict[str, object]) -> dict[str, object]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(f"{self._base}/{method}", data=data, headers={"Content-Type": "application/json"}, method="POST")
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                with urlopen(request, timeout=self._timeout) as response:
                    body = response.read().decode("utf-8")
                result = json.loads(body)
                if not isinstance(result, dict):
                    raise TelegramApiError("Telegram response must be an object")
                if not result.get("ok"):
                    raise TelegramApiError(str(result.get("description", "Telegram API error")))
                return result
            except HTTPError as error:
                if error.code in {400, 401, 403}:
                    raise TelegramApiError(f"Telegram HTTP {error.code}") from error
                last_error = TelegramHttpError(f"Telegram HTTP {error.code}")
            except (URLError, TimeoutError, json.JSONDecodeError, TelegramTransportError) as error:
                last_error = error
            if attempt < self._retries:
                self._sleeper(min(2.0, 0.25 * (2 ** attempt)))
        raise TelegramTransportError("Telegram request failed after retries") from last_error


@dataclass(frozen=True, slots=True)
class PollingResult:
    polls: int
    updates_received: int
    updates_processed: int
    responses_sent: int
    transport_errors: int


class TelegramPoller:
    def __init__(self, client: TelegramApiClient, adapter: TelegramAdapter, *, sleeper: Callable[[float], None] = time.sleep) -> None:
        self._client = client
        self._adapter = adapter
        self._sleeper = sleeper
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run(self, *, max_cycles: int | None = None, poll_timeout: int = 20) -> PollingResult:
        offset: int | None = None
        polls = received = processed = sent = errors = 0
        while not self._stopped and (max_cycles is None or polls < max_cycles):
            polls += 1
            try:
                updates = self._client.get_updates(offset, timeout=poll_timeout)
            except TelegramTransportError:
                errors += 1
                self._sleeper(0.5)
                continue
            received += len(updates)
            for update in updates:
                update_id = update.get("update_id")
                try:
                    outbound = self._adapter.handle_update(update)
                    self._client.send(outbound)
                except TelegramInputError:
                    processed += 1
                except (TelegramTransportError, TelegramApiError):
                    errors += 1
                    continue
                processed += 1
                sent += 1
                if isinstance(update_id, int):
                    offset = max(offset or update_id + 1, update_id + 1)
        return PollingResult(polls, received, processed, sent, errors)
