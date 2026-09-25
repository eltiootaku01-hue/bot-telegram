# -*- coding: utf-8 -*-
"""Seguridad inmersiva de Discord: bienvenida, cooldown, strikes y SuperAdmin."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import threading
import time
from typing import Callable


WELCOME_CHANNEL_KEY = "bienvenida"
WELCOME_RULES_TITLE = "🐭 Chie · Bienvenido al Café"
WELCOME_RULES_TEXT = (
    "Sé un buen nakama. Respeta a los demás, evita spam y sigue las reglas "
    "del servidor. Confirma que eres Usuario para recibir acceso general."
)
WELCOME_COOLDOWN_SECONDS = 15.0
STRIKE_TIMEOUT_SECONDS = 60 * 60
TRANSIENT_BOT_MESSAGE_SECONDS = 20
WEEKLY_PURGE_SECONDS = 7 * 24 * 60 * 60
SUPERADMIN_TELEGRAM = "@tiootakuu"
SUPERADMIN_TELEGRAM_URL = "https://t.me/tiootakuu"


@dataclass(frozen=True, slots=True)
class WelcomeDecision:
    action: str
    message: str
    grant_role: bool = False
    kick: bool = False


@dataclass(frozen=True, slots=True)
class StrikeRecord:
    user_id: str
    strikes: int
    reason: str
    updated_at: str


class BurstGate:
    """Rate gate O(1) para ráfagas; no duerme ni bloquea el event loop."""

    def __init__(self, *, max_events: int = 15, window_seconds: float = 15.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.max_events = max(1, int(max_events))
        self.window_seconds = float(window_seconds)
        self._clock = clock
        self._events: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        safe_key = str(key)
        with self._lock:
            values = [stamp for stamp in self._events.get(safe_key, ()) if now - stamp < self.window_seconds]
            if len(values) >= self.max_events:
                self._events[safe_key] = values
                return False
            values.append(now)
            self._events[safe_key] = values
            return True

    def clear(self, key: str) -> None:
        with self._lock:
            self._events.pop(str(key), None)


class WelcomeGate:
    """Cooldown real: durante 15 s cualquier nuevo input se ignora."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._pending: dict[str, float] = {}

    def start(self, user_id: str) -> bool:
        now = self._clock()
        with self._lock:
            until = self._pending.get(str(user_id), 0.0)
            if until > now:
                return False
            self._pending[str(user_id)] = now + WELCOME_COOLDOWN_SECONDS
            return True

    def choose(self, user_id: str, choice: str) -> WelcomeDecision:
        uid = str(user_id)
        with self._lock:
            self._pending.pop(uid, None)
        normalized = str(choice).strip().casefold()
        if normalized == "bot":
            return WelcomeDecision(
                "kick",
                "🤖 Chie: Has elegido Bot. El acceso general será retirado.",
                kick=True,
            )
        if normalized != "usuario":
            return WelcomeDecision("ignore", "⏳ Chie: selección no válida.")
        return WelcomeDecision(
            "grant",
            "🐭 Chie: ¡Bienvenido, nakama! Acceso general concedido.",
            grant_role=True,
        )

    def ignore_during_cooldown(self, user_id: str) -> bool:
        return self._clock() < self._pending.get(str(user_id), 0.0)


class StrikeStore:
    """Persistencia atómica y sencilla de strikes por servidor/usuario."""

    def __init__(self, root: Path) -> None:
        self.path = Path(root) / "config" / "discord_strikes.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _load(self) -> dict[str, object]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def _save(self, value: dict[str, object]) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def add(self, guild_id: str, user_id: str, reason: str) -> StrikeRecord:
        key = f"{guild_id}:{user_id}"
        with self._lock:
            data = self._load()
            old = data.get(key, {})
            strikes = int(old.get("strikes", 0)) + 1 if isinstance(old, dict) else 1
            record = StrikeRecord(
                str(user_id),
                strikes,
                str(reason).strip()[:500],
                datetime.now(timezone.utc).isoformat(),
            )
            data[key] = {
                "user_id": record.user_id,
                "strikes": record.strikes,
                "reason": record.reason,
                "updated_at": record.updated_at,
            }
            self._save(data)
            return record

    def get(self, guild_id: str, user_id: str) -> StrikeRecord | None:
        with self._lock:
            item = self._load().get(f"{guild_id}:{user_id}")
        if not isinstance(item, dict):
            return None
        return StrikeRecord(
            str(item.get("user_id", user_id)),
            int(item.get("strikes", 0)),
            str(item.get("reason", "")),
            str(item.get("updated_at", "")),
        )


class ImmersiveStrikeEngine:
    """Strike 1/2/3 y ráfaga; el SuperAdmin queda fuera de sanciones."""

    def __init__(self, store: StrikeStore, *, superadmin: str = SUPERADMIN_TELEGRAM) -> None:
        self.store = store
        configured = superadmin or os.getenv("TELEGRAM_SUPERADMIN_USERNAME", SUPERADMIN_TELEGRAM)
        self.superadmin = configured.casefold().lstrip("@")
        self.discord_superadmin_id = os.getenv("DISCORD_SUPERADMIN_USER_ID", "").strip()

    def is_superadmin(self, user_id: str, username: str = "") -> bool:
        return (
            bool(self.discord_superadmin_id) and str(user_id) == self.discord_superadmin_id
        ) or str(username).casefold().lstrip("@") == self.superadmin

    def evaluate(self, guild_id: str, user_id: str, reason: str, *, username: str = "", burst: bool = False) -> StrikeRecord | None:
        if self.is_superadmin(user_id, username):
            return None
        record = self.store.add(guild_id, user_id, reason)
        if burst and record.strikes < 3:
            # La ráfaga fuerza la rama de aislamiento sin alterar el contador artificialmente.
            return StrikeRecord(record.user_id, 3, "spam/burst: " + record.reason, record.updated_at)
        return record

    @staticmethod
    def action_for(record: StrikeRecord | None) -> str:
        if record is None:
            return "immune"
        if record.strikes >= 3:
            return "isolate"
        if record.strikes == 2:
            return "timeout"
        return "warn_delete"

    @staticmethod
    def cari_message(record: StrikeRecord | None) -> str:
        if record is None:
            return "🦫 Cari: Tu mensaje fue retirado preventivamente para mantener el café seguro."
        if record.strikes >= 3:
            return "🦫 Cari: Me pone triste tener que aislar esta cuenta. Elige una acción con el Admin."
        if record.strikes == 2:
            return "🦫 Cari: Estoy triste... has recibido tu segundo strike. Quedas en silencio durante 1 hora."
        return "🦫 Cari: Por favor, cuida las reglas del Café. He retirado tu mensaje como primera advertencia."


def welcome_embed_payload() -> dict[str, object]:
    return {
        "title": WELCOME_RULES_TITLE,
        "description": WELCOME_RULES_TEXT,
        "color": 0xF2C14E,
        "components": (
            {
                "type": 1,
                "components": (
                    {"type": 2, "style": 3, "label": "👤 Usuario", "custom_id": "welcome:user"},
                    {"type": 2, "style": 4, "label": "🤖 Bot", "custom_id": "welcome:bot"},
                ),
            },
        ),
    }


def admin_strike_actions(user_id: str) -> tuple[tuple[str, str], ...]:
    return (
        ("🔨 Ban", f"strike:ban:{user_id}"),
        ("👢 Kick", f"strike:kick:{user_id}"),
        ("💗 Perdonar", f"strike:forgive:{user_id}"),
    )


def should_purge(last_activity: float, *, now: float | None = None, inactivity_seconds: float = WEEKLY_PURGE_SECONDS) -> bool:
    current = time.time() if now is None else float(now)
    return current - float(last_activity) >= float(inactivity_seconds)


class DiscordWelcomeHandler:
    """Contrato de interacción para los botones de bienvenida."""

    def __init__(self, gate: WelcomeGate | None = None) -> None:
        self.gate = gate or WelcomeGate()

    def on_member_join(self, user_id: str) -> WelcomeDecision:
        if not self.gate.start(user_id):
            return WelcomeDecision("ignore", "⏳ Chie: bienvenida en cooldown.")
        return WelcomeDecision("prompt", WELCOME_RULES_TEXT)

    def on_button(self, user_id: str, custom_id: str) -> WelcomeDecision:
        if self.gate.ignore_during_cooldown(user_id):
            return WelcomeDecision("ignore", "⏳ Chie: espera 15 segundos antes de responder.")
        choice = "usuario" if custom_id == "welcome:user" else "bot" if custom_id == "welcome:bot" else ""
        return self.gate.choose(user_id, choice)


class DiscordStrikeHandler:
    """Convierte una infracción en acciones REST sin bloquear el listener."""

    def __init__(self, engine: ImmersiveStrikeEngine) -> None:
        self.engine = engine

    def handle(self, guild_id: str, user_id: str, reason: str, *, username: str = "", burst: bool = False) -> dict[str, object]:
        record = self.engine.evaluate(guild_id, user_id, reason, username=username, burst=burst)
        action = self.engine.action_for(record)
        return {
            "action": action,
            "strikes": record.strikes if record else 0,
            "message": self.engine.cari_message(record),
            "admin_actions": admin_strike_actions(user_id) if action == "isolate" else (),
            "superadmin_immune": action == "immune",
        }
