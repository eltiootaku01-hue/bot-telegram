# -*- coding: utf-8 -*-
"""Inmersión local del Café Otaku: personalidades y Hora del Té."""

from __future__ import annotations

from dataclasses import dataclass
from random import SystemRandom
import threading
import time
from typing import Callable


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


def waitress_dialogue(maid: str, event: str = "greeting") -> str:
    name = normalize_maid(maid)
    profile = WAITRESS_PROFILES[name]
    if event == "tea":
        return profile["tea"]
    if event == "role":
        return f"{name}: {profile['focus']}."
    return profile["greeting"]


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
