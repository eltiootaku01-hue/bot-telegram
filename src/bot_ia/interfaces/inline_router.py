# -*- coding: utf-8 -*-
"""Respuestas Inline externas con rate-limit y bloqueo anti-abuso."""

from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass(frozen=True, slots=True)
class InlineResult:
    text: str
    button_label: str
    button_url: str
    blocked: bool = False


class InlineAbuseGuard:
    def __init__(self, *, limit: int = 3, window_seconds: float = 60.0) -> None:
        self.limit = max(1, int(limit))
        self.window_seconds = max(1.0, float(window_seconds))
        self._events: dict[str, list[float]] = {}
        self._blocked: set[str] = set()

    def check(self, user_id: str, *, official: bool, now: float | None = None) -> InlineResult | None:
        if official:
            return None
        uid = str(user_id)
        if uid in self._blocked:
            return InlineResult("Inline bloqueado por abuso repetido. Revisa las incidencias del Café.", "☕ Ir al Café Otaku", "", True)
        current = time.monotonic() if now is None else float(now)
        events = [stamp for stamp in self._events.get(uid, []) if current - stamp < self.window_seconds]
        if len(events) >= self.limit:
            self._events[uid] = events
            self._blocked.add(uid)
            return InlineResult("Demasiadas consultas Inline fuera de la comunidad. Se bloqueó temporalmente el acceso Inline.", "☕ Ir al Café Otaku", "", True)
        events.append(current)
        self._events[uid] = events
        return None

    def is_blocked(self, user_id: str) -> bool:
        return str(user_id) in self._blocked


class InlineRedirectHandler:
    def __init__(self, *, official_ids: set[str] | frozenset[str], cafe_url: str, incidents=None) -> None:
        self._official_ids = frozenset(str(value) for value in official_ids)
        self._cafe_url = str(cafe_url)
        self._guard = InlineAbuseGuard()
        self._incidents = incidents

    def handle(self, *, user_id: str, query: str = "", chat_id: str | None = None) -> InlineResult:
        official = str(chat_id) in self._official_ids if chat_id is not None else False
        result = self._guard.check(user_id, official=official)
        if result is not None:
            if result.blocked and self._incidents is not None:
                self._incidents.record(
                    category="Inline Abuse",
                    user_id=str(user_id),
                    rule=">3 consultas Inline/minuto fuera de la comunidad",
                    detail=query[:500],
                )
            return InlineResult(result.text, result.button_label, self._cafe_url, True)
        return InlineResult(
            'Cari: "Oh... ¿me seguiste hasta aquí?" ☕',
            "☕ Ir al Café Otaku",
            self._cafe_url,
            False,
        )
