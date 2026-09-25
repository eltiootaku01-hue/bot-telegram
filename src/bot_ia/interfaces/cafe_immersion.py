# -*- coding: utf-8 -*-
"""Inmersión local del Café Otaku: personalidades y Hora del Té."""

from __future__ import annotations


import asyncio
import base64
from pathlib import Path

AVATAR_DIR = Path(__file__).resolve().parents[3] / "assets" / "avatars"
DEFAULT_AVATAR = AVATAR_DIR / "default.png"
AVATAR_FILENAMES = {"Cari": "cari.png", "Cami": "cami.png", "Sunna": "sunna.png", "Chie": "chie.png", "Scarlet": "scarlet.png", "Chloé": "chloe.png"}

def waitress_avatar_path(name: str) -> Path:
    candidate = AVATAR_DIR / AVATAR_FILENAMES.get(name, "default.png")
    return candidate if candidate.is_file() else DEFAULT_AVATAR

def waitress_avatar_data_uri(name: str) -> str | None:
    path = waitress_avatar_path(name)
    if not path.is_file():
        return None
    try:
        payload = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return None
    return "data:image/png;base64," + payload


from dataclasses import dataclass
from random import SystemRandom
import threading
import time
from typing import Callable
from .cami_guard import CamiGuardDecision, scan_cami_guard, is_superadmin


WAITRESS_PROFILES = {
    "Cari": {
        "role": "Maid clásica",
        "focus": "Servicio clásico Maid & Gacha",
        "greeting": "☕ Cari: ¡Bienvenido, maestro! Tu servicio Maid y tu próxima tirada quedan bajo mi cuidado.",
        "tea": "🍰 Cari: ¡Hora del Té! Un buen servicio merece puntos extra.",
    },
    "Sunna": {
        "role": "Anfitriona competitiva",
        "focus": "21 / Blackjack",
        "greeting": "🃏 Sunna: La mesa está lista. Si vienes por 21, juega con cabeza y sin miedo.",
        "tea": "🃏 Sunna: Hora del Té activa. ¡Doblemos la recompensa de la mesa!",
    },
    "Cami": {
        "role": "Barista",
        "focus": "Bebidas especiales y prompts",
        "greeting": "🥤 Cami: Puedo preparar una bebida especial y convertir tu idea en un prompt preciso.",
        "tea": "🥤 Cami: La Hora del Té llegó. Una bebida bien servida sabe mejor con puntos dobles.",
    },
    "Chie": {
        "role": "Encargada de trivias",
        "focus": "Trivias e isekai debates",
        "greeting": "📚 Chie: Trae tu trivia o tu debate isekai. Yo preparo la mesa y las preguntas.",
        "tea": "📚 Chie: Hora del Té. ¡Que empiece el debate y que los puntos se dupliquen!",
    },
    "Scarlet": {
        "role": "Anfitriona de Cantina +18",
        "focus": "21 / Blackjack y mesa de apuestas",
        "greeting": "🍷 Scarlet: La mesa de la Cantina está preparada. Yo superviso el 21 y las apuestas.",
        "tea": "🍷 Scarlet: Hora del Té en la Cantina. La mesa queda con recompensas dobles.",
    },
    "Chloé": {
        "role": "Anfitriona de Cantina +18",
        "focus": "Apuestas y pedidos NSFW",
        "greeting": "🍷 Chloé: Bienvenido a la Cantina. Puedo ayudarte con la mesa de apuestas y los pedidos para adultos.",
        "tea": "🍷 Chloé: La Hora del Té también llegó a la Cantina. Que empiece la partida.",
    },
}


COMMENT_REPLY_TEXT = "¡Gracias por comentar, Nakama! ☕"
DISCORD_COMMENT_THREAD_NAME = "💬 Comentarios"
COMMENT_MAX_LENGTH = 280


@dataclass(frozen=True, slots=True)
class TelegramCommentDecision:
    should_reply: bool
    chat_id: str
    reply_to_message_id: int | None = None
    text: str = COMMENT_REPLY_TEXT


@dataclass(frozen=True, slots=True)
class DiscordThreadDecision:
    should_create: bool
    channel_id: str
    thread_name: str = DISCORD_COMMENT_THREAD_NAME


def analyze_telegram_comment(update: dict[str, object]) -> TelegramCommentDecision:
    """Detecta comentarios del grupo vinculado sin responder a otros bots ni a comandos."""
    message = update.get("message")
    if not isinstance(message, dict):
        return TelegramCommentDecision(False, "", None)
    chat = message.get("chat")
    sender = message.get("from")
    if not isinstance(chat, dict) or not isinstance(sender, dict):
        return TelegramCommentDecision(False, "", None)
    if bool(sender.get("is_bot")):
        return TelegramCommentDecision(False, str(chat.get("id", "")), None)
    text = str(message.get("text", "") or "").strip()
    if not text or text.startswith("/"):
        return TelegramCommentDecision(False, str(chat.get("id", "")), None)
    reply = message.get("reply_to_message")
    reply_id = reply.get("message_id") if isinstance(reply, dict) else None
    if not isinstance(reply_id, int) or reply_id <= 0:
        return TelegramCommentDecision(False, str(chat.get("id", "")), None)
    return TelegramCommentDecision(True, str(chat.get("id", "")), reply_id)


def analyze_discord_announcement(
    *,
    author_id: str,
    superadmin_id: str,
    channel_id: str,
    is_announcement_channel: bool,
    is_bot: bool = False,
) -> DiscordThreadDecision:
    if is_bot or str(author_id) != str(superadmin_id) or not is_announcement_channel:
        return DiscordThreadDecision(False, str(channel_id))
    return DiscordThreadDecision(True, str(channel_id))


class DiscordCommentThreadManager:
    """Crea un único hilo de comentarios por publicación del SuperAdmin."""

    def __init__(self, discord_client: object) -> None:
        self._client = discord_client
        self._created: set[str] = set()

    def on_announcement(
        self,
        *,
        author_id: str,
        superadmin_id: str,
        channel_id: str,
        message_id: str,
        is_announcement_channel: bool,
        is_bot: bool = False,
    ) -> dict[str, object] | None:
        decision = analyze_discord_announcement(
            author_id=author_id,
            superadmin_id=superadmin_id,
            channel_id=channel_id,
            is_announcement_channel=is_announcement_channel,
            is_bot=is_bot,
        )
        if not decision.should_create or str(message_id) in self._created:
            return None
        creator = getattr(self._client, "create_comment_thread", None)
        if not callable(creator):
            raise TypeError("Discord client must provide create_comment_thread")
        thread = creator(channel_id, message_id, name=decision.thread_name)
        self._created.add(str(message_id))
        return thread




def normalize_maid(maid: str) -> str:
    value = str(maid or "").strip().casefold()
    for name in WAITRESS_PROFILES:
        if name.casefold() == value:
            return name
    return "Cami"


def waitress_profile(maid: str) -> dict[str, str]:
    return dict(WAITRESS_PROFILES[normalize_maid(maid)])


def waitress_exclusive_dialogue(maid: str, heart_level: int) -> str:
    name = normalize_maid(maid)
    level = max(0, int(heart_level))
    if level < 3:
        return ""
    messages = {
        "Cari": "💗 Cari: Maestro, gracias por confiar en mí. Esta atención especial queda entre nosotros.",
        "Sunna": "💗 Sunna: Con este Heart Level ya tienes mi desafío especial: demuestra que puedes superar la mesa.",
        "Cami": "💗 Cami: Tu afinidad desbloqueó mi receta especial. Vamos a cuidar cada detalle del próximo prompt.",
        "Chie": "💗 Chie: Tu afinidad desbloqueó mi pregunta secreta. Prepárate para un debate isekai de nivel avanzado.",
    }
    return messages[name]


def waitress_dialogue(
    maid: str,
    event: str = "greeting",
    *,
    chat_title: str | None = None,
) -> str:
    name = normalize_maid(maid)
    profile = WAITRESS_PROFILES[name]
    place = str(chat_title or "").strip()
    prefix = f"☕ {place} · " if place else ""
    if event == "tea":
        return prefix + profile["tea"]
    if event == "role":
        return f"{prefix}{name}: {profile['focus']}."
    return prefix + profile["greeting"]


def resolve_chat_title(platform: str, chat: object) -> str:
    """Obtiene el nombre real de Telegram/Discord sin depender de un nombre fijo."""
    network = str(platform).strip().casefold()
    if isinstance(chat, dict):
        key = "title" if network == "telegram" else "name"
        value = chat.get(key)
        if value:
            return str(value).strip()
    return ""


def waitress_chat_title(platform: str, chat: object) -> str:
    return resolve_chat_title(platform, chat)

# Estado multiplataforma de las meseras.
BUSY_EVENT_TIMEOUT_SECONDS = 60.0
OPPOSITE_NETWORK_LINKS = {
    "Telegram": "https://t.me/eltiootaku",
    "Discord": "https://discord.gg/eltiootaku",
}


@dataclass(frozen=True, slots=True)
class WaitressBusyState:
    maid: str
    platform: str
    busy_until: float
    event_id: str

    @property
    def busy(self) -> bool:
        return self.busy_until > time.monotonic()


class WaitressPresenceManager:
    """Presencia multiplataforma con límite duro de 60 segundos por evento."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.RLock()
        self._states: dict[str, WaitressBusyState] = {}

    def acquire(self, maid: str, platform: str, event_id: str, timeout: float = BUSY_EVENT_TIMEOUT_SECONDS) -> bool:
        name = normalize_maid(maid)
        network = str(platform).strip().title()
        if network not in OPPOSITE_NETWORK_LINKS or timeout <= 0:
            raise ValueError("platform or timeout is invalid")
        now = self._clock()
        with self._lock:
            state = self._states.get(name)
            if state is not None and state.busy_until > now:
                return False
            self._states[name] = WaitressBusyState(
                name,
                network,
                now + min(float(timeout), BUSY_EVENT_TIMEOUT_SECONDS),
                str(event_id),
            )
            return True

    def release(self, maid: str, event_id: str | None = None) -> None:
        name = normalize_maid(maid)
        with self._lock:
            state = self._states.get(name)
            if state is not None and (event_id is None or state.event_id == str(event_id)):
                self._states.pop(name, None)

    def state(self, maid: str) -> WaitressBusyState | None:
        name = normalize_maid(maid)
        now = self._clock()
        with self._lock:
            state = self._states.get(name)
            if state is not None and state.busy_until <= now:
                self._states.pop(name, None)
                return None
            return state

    def encargado_message(self, maid: str, requesting_platform: str) -> str | None:
        state = self.state(maid)
        if state is None:
            return None
        opposite = state.platform
        link = OPPOSITE_NETWORK_LINKS[opposite]
        return (
            f"Disculpe, cliente-sama. {state.maid} se encuentra en nuestro grupo de "
            f"{opposite} ({link}) atendiendo a un cliente. Volverá en breve."
        )

    def sweep_expired(self) -> int:
        now = self._clock()
        with self._lock:
            expired = [name for name, state in self._states.items() if state.busy_until <= now]
            for name in expired:
                self._states.pop(name, None)
            return len(expired)


class AsyncBusyGuard:
    """Guarda no bloqueante: libera automáticamente cada evento a los 60 s."""

    def __init__(self, *, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop
        self._events: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str, timeout: float = BUSY_EVENT_TIMEOUT_SECONDS) -> bool:
        safe_key = str(key).strip()
        if not safe_key:
            raise ValueError("busy key cannot be empty")
        bounded = min(float(timeout), BUSY_EVENT_TIMEOUT_SECONDS)
        if bounded <= 0:
            raise ValueError("timeout must be positive")
        async with self._lock:
            task = self._events.get(safe_key)
            if task is not None and not task.done():
                return False
            self._events[safe_key] = asyncio.create_task(self._auto_release(safe_key, bounded))
            return True

    async def _auto_release(self, key: str, timeout: float) -> None:
        try:
            await asyncio.sleep(timeout)
        except asyncio.CancelledError:
            return
        async with self._lock:
            self._events.pop(key, None)

    async def release(self, key: str) -> None:
        async with self._lock:
            task = self._events.pop(str(key), None)
            if task is not None and not task.done():
                task.cancel()

    async def busy(self, key: str) -> bool:
        async with self._lock:
            task = self._events.get(str(key))
            return task is not None and not task.done()

    async def close(self) -> None:
        async with self._lock:
            tasks = tuple(self._events.values())
            self._events.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


def supervise_admin_publication(
    text: object,
    *,
    image_tags: tuple[str, ...] = (),
    user_id: object = "",
    username: object = "",
    content_kind: str = "text",
    target_room: str = "#general",
) -> CamiGuardDecision:
    """Punto único de entrada de Cami Guard para publicaciones del administrador."""
    return scan_cami_guard(
        text,
        image_tags=image_tags,
        user_id=user_id,
        username=username,
        content_kind=content_kind,
        target_room=target_room,
    )


def superadmin_is_immune(user_id: object = "", username: object = "") -> bool:
    return is_superadmin(user_id, username)



TEA_TIME_DURATION_SECONDS = 20 * 60
TEA_TIME_MIN_INTERVAL_SECONDS = 30 * 60
TEA_TIME_MAX_INTERVAL_SECONDS = 90 * 60
TEA_TIME_MULTIPLIER = 2


@dataclass(frozen=True, slots=True)
class TeaTimeState:
    active_until: float = 0.0

    @property
    def active(self) -> bool:
        return self.active_until > time.time()


class TeaTimeScheduler:
    """Scheduler local y detenible; no usa red ni bloquea el hilo de la GUI."""

    def __init__(
        self,
        *,
        random_source: object | None = None,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] | None = None,
        min_interval_seconds: float = TEA_TIME_MIN_INTERVAL_SECONDS,
        max_interval_seconds: float = TEA_TIME_MAX_INTERVAL_SECONDS,
    ) -> None:
        if min_interval_seconds <= 0 or max_interval_seconds < min_interval_seconds:
            raise ValueError("Tea Time interval is invalid")
        self._random = random_source or SystemRandom()
        self._clock = clock
        self._sleeper = sleeper or time.sleep
        self._min_interval = float(min_interval_seconds)
        self._max_interval = float(max_interval_seconds)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._active_until = 0.0
        self._thread: threading.Thread | None = None

    def is_active(self, now: float | None = None) -> bool:
        current = self._clock() if now is None else float(now)
        with self._lock:
            return self._active_until > current

    def multiplier(self, now: float | None = None) -> int:
        return TEA_TIME_MULTIPLIER if self.is_active(now) else 1

    def remaining_seconds(self, now: float | None = None) -> int:
        current = self._clock() if now is None else float(now)
        with self._lock:
            return max(0, int(self._active_until - current))

    def status_text(self, now: float | None = None) -> str:
        remaining = self.remaining_seconds(now)
        if remaining <= 0:
            return "🍰 Hora del Té: inactiva."
        return f"🍰 Hora del Té activa: puntos de minijuegos x{TEA_TIME_MULTIPLIER} durante {remaining // 60} min."

    def activate(self, *, now: float | None = None, duration_seconds: float = TEA_TIME_DURATION_SECONDS) -> TeaTimeState:
        if duration_seconds <= 0:
            raise ValueError("Tea Time duration must be positive")
        current = self._clock() if now is None else float(now)
        with self._lock:
            self._active_until = current + float(duration_seconds)
            return TeaTimeState(self._active_until)

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="CafeOtakuTeaTime",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, float(timeout)))
        self._thread = None

    def _random_interval(self) -> float:
        return float(self._random.uniform(self._min_interval, self._max_interval))

    def _run(self) -> None:
        while not self._stop.wait(self._random_interval()):
            self.activate()
            if self._stop.wait(TEA_TIME_DURATION_SECONDS):
                return
            with self._lock:
                self._active_until = 0.0
