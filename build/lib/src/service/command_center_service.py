from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from aiogram import Bot
from src.db.event_repository import EventRepository

from fastapi import Depends, FastAPI, Header, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from src.config.topic_mapper import resolve_topic_for_event
from src.service.bootstrap import GroupBootstrapper, InsufficientPermissionsError
from src.service.event_recovery import recover_orphan_events
from src.service.notification_dispatcher import TelegramNotificationDispatcher

logger = logging.getLogger(__name__)
DispatchNotification = Callable[[int, "WebhookPayload"], Awaitable[None]]


@dataclass(slots=True)
class NotificationDispatcher:
    send: DispatchNotification

    async def dispatch(self, thread_id: int, payload: "WebhookPayload") -> None:
        await self.send(thread_id, payload)


_dispatcher: Optional[NotificationDispatcher] = None
_runtime_telegram_dispatcher: TelegramNotificationDispatcher | None = None
_event_repository: EventRepository | None = None


def _parse_telegram_chat_id(value: str) -> int:
    if not value.strip():
        return 0
    try:
        return int(value.strip())
    except ValueError:
        logger.error("TELEGRAM_COMMUNITY_CHAT_ID inválido: debe ser un entero.")
        return 0


def configure_notification_dispatcher(dispatcher: NotificationDispatcher | None) -> None:
    global _dispatcher
    _dispatcher = dispatcher


def get_auth_token() -> str:
    token = os.getenv("COMMAND_CENTER_TOKEN")
    if not token:
        raise RuntimeError("CRITICAL: COMMAND_CENTER_TOKEN env variable is missing!")
    return token


def verify_bearer_token(
    authorization: Optional[str] = Header(default=None),
    expected_token: str = Depends(get_auth_token),
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Header Authorization con formato 'Bearer <token>' es requerido.", headers={"WWW-Authenticate": "Bearer"})
    scheme, _, provided_token = authorization.partition(" ")
    if scheme != "Bearer" or not provided_token or " " in provided_token:
        raise HTTPException(status_code=401, detail="Bearer token inválido.", headers={"WWW-Authenticate": "Bearer"})
    if not secrets.compare_digest(provided_token, expected_token):
        raise HTTPException(status_code=401, detail="Bearer token inválido.", headers={"WWW-Authenticate": "Bearer"})


class WebhookPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    event_type: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=300)
    url: HttpUrl
    author: str = Field(default="Anónimo", min_length=1, max_length=120)
    event_id: str | None = Field(default=None, min_length=1, max_length=128)


class EventStatusResponse(BaseModel):
    event_id: str
    event_type: str
    bot_name: str
    thread_id: int
    title: str
    url: str
    author: str
    status: str
    retry_count: int
    max_retries: int
    telegram_message_id: int | None = None
    last_error: str | None = None
    created_at: str
    updated_at: str


class BootstrapRequest(BaseModel):
    chat_id: int


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _runtime_telegram_dispatcher, _event_repository
    get_auth_token()
    db_path = os.getenv("COMMAND_CENTER_EVENT_DB_PATH", os.getenv("COMMAND_CENTER_DB_PATH", "data/command_center_events.db"))
    _event_repository = EventRepository(db_path)
    await _event_repository.init_db()
    tokens = {"chie": os.getenv("BOT_TOKEN_CHIE", ""), "sunna": os.getenv("BOT_TOKEN_SUNNA", "")}
    chat_id = _parse_telegram_chat_id(os.getenv("TELEGRAM_COMMUNITY_CHAT_ID", "0"))
    event_bot_map: dict[str, str] = {}
    raw_event_bot_map = os.getenv("COMMAND_CENTER_EVENT_BOT_MAP", "")
    if raw_event_bot_map:
        try:
            decoded = json.loads(raw_event_bot_map)
        except json.JSONDecodeError as exc:
            raise RuntimeError("COMMAND_CENTER_EVENT_BOT_MAP must contain valid JSON.") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("COMMAND_CENTER_EVENT_BOT_MAP must be a JSON object.")
        event_bot_map = {str(event): str(bot) for event, bot in decoded.items()}
    configured_tokens = {name: token for name, token in tokens.items() if token}
    if chat_id and configured_tokens and event_bot_map:
        telegram_dispatcher = TelegramNotificationDispatcher(bot_tokens=configured_tokens, target_chat_id=chat_id, event_bot_map=event_bot_map, event_repository=_event_repository)
        await telegram_dispatcher.start()
        _runtime_telegram_dispatcher = telegram_dispatcher
        configure_notification_dispatcher(telegram_dispatcher)
        recovered_count = await recover_orphan_events(_event_repository, telegram_dispatcher)
        logger.info("Reencolados %d evento(s) pendientes desde SQLite.", recovered_count)
    elif os.getenv("COMMAND_CENTER_REQUIRE_TELEGRAM", "").casefold() == "true":
        raise RuntimeError("Telegram dispatcher required but BOT_TOKEN_*, TELEGRAM_COMMUNITY_CHAT_ID and COMMAND_CENTER_EVENT_BOT_MAP are incomplete.")
    try:
        yield
    finally:
        if _runtime_telegram_dispatcher is not None:
            configure_notification_dispatcher(None)
            await _runtime_telegram_dispatcher.stop(drain_timeout=5.0)
            _runtime_telegram_dispatcher = None


app = FastAPI(title="CommandCenterService API", version="1.0.0", lifespan=lifespan)


@app.post("/api/v1/system/bootstrap", status_code=status.HTTP_200_OK, summary="Inicializar automáticamente los Forum Topics del grupo")
async def bootstrap_system(payload: BootstrapRequest, _: None = Depends(verify_bearer_token)) -> dict[str, object]:
    token = os.getenv("TELEGRAM_BOOTSTRAP_BOT_TOKEN")
    if not token:
        raise HTTPException(status_code=503, detail="TELEGRAM_BOOTSTRAP_BOT_TOKEN no está configurado.")
    bootstrapper = GroupBootstrapper(os.getenv("COMMAND_CENTER_EVENT_DB_PATH", os.getenv("COMMAND_CENTER_DB_PATH", "data/command_center_events.db")))
    bot = Bot(token=token)
    try:
        return await bootstrapper.run_bootstrap(payload.chat_id, bot)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InsufficientPermissionsError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Group bootstrap failed for chat_id=%s", payload.chat_id)
        raise HTTPException(status_code=502, detail="Telegram group bootstrap failed.") from exc
    finally:
        await bot.session.close()


@app.post("/api/v1/notifications/webhook", status_code=status.HTTP_200_OK)
async def handle_web_notification(payload: WebhookPayload, _: None = Depends(verify_bearer_token)) -> dict[str, object]:
    thread = resolve_topic_for_event(payload.event_type)
    if thread is None:
        raise HTTPException(status_code=400, detail=f"Tipo de evento no reconocido: '{payload.event_type}'")
    dispatcher = _dispatcher
    if dispatcher is None:
        raise HTTPException(status_code=503, detail="La pasarela de Telegram no está configurada.")
    event_id = payload.event_id or hashlib.sha256(f"{payload.event_type}|{payload.title}|{payload.url}|{payload.author}".encode("utf-8")).hexdigest()
    raw_mapping = os.getenv("COMMAND_CENTER_EVENT_BOT_MAP", "")
    try:
        mapping = json.loads(raw_mapping) if raw_mapping else {}
        resolved_bot_name = str(mapping.get(payload.event_type, "command-center"))
    except (json.JSONDecodeError, AttributeError):
        resolved_bot_name = "command-center"
    repository = _event_repository
    if repository is not None:
        inserted = await repository.create_event(event_id=event_id, event_type=payload.event_type, bot_name=resolved_bot_name, thread_id=thread.value, title=payload.title, url=str(payload.url), author=payload.author)
        if not inserted:
            existing = await repository.get_event(event_id)
            if existing and existing["status"] == "DELIVERED":
                return {"status": "success", "message": "Evento ya entregado; solicitud duplicada ignorada.", "event_id": event_id, "target_thread_id": thread.value}
            return {"status": "success", "message": "Evento ya registrado y pendiente de procesamiento.", "event_id": event_id, "target_thread_id": thread.value}
    try:
        await dispatcher.dispatch(thread.value, payload.model_copy(update={"event_id": event_id}))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Telegram notification dispatch failed")
        raise HTTPException(status_code=503, detail="Fallo en la comunicación con la API de Telegram.") from exc
    return {"status": "success", "message": "Notificación registrada y encolada para Telegram.", "event_id": event_id, "target_thread_id": thread.value}


@app.get("/api/v1/notifications/events/{event_id}", response_model=EventStatusResponse)
async def get_notification_event_status(event_id: str = Path(min_length=1, max_length=128), _: None = Depends(verify_bearer_token)) -> EventStatusResponse:
    repository = _event_repository
    if repository is None:
        raise HTTPException(status_code=503, detail="El almacén de eventos no está inicializado.")
    event = await repository.get_event_by_id(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Evento no encontrado: '{event_id}'")
    return EventStatusResponse.model_validate(event)


def main() -> None:
    import uvicorn
    uvicorn.run("src.service.command_center_service:app", host=os.getenv("COMMAND_CENTER_HOST", "127.0.0.1"), port=int(os.getenv("COMMAND_CENTER_PORT", "8770")))


if __name__ == "__main__":
    main()
