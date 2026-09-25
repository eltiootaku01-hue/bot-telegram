# -*- coding: utf-8 -*-
"""Presencia multiplataforma y enrutamiento seguro de interacciones de meseras."""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Literal

Platform = Literal["telegram", "discord"]


@dataclass(frozen=True, slots=True)
class WaitressPresence:
    waitress: str
    platform: Platform
    action: str
    started_at: float
    active: bool = True


@dataclass(frozen=True, slots=True)
class PresenceReply:
    occupied: bool
    message: str
    platform: Platform | None = None


class WaitressPresenceManager:
    """Estado en memoria, thread-safe, con transferencia de interacciones."""

    def __init__(self, *, clock=time.time) -> None:
        self._clock = clock
        self._lock = threading.RLock()
        self._active: dict[str, WaitressPresence] = {}
        self._transferred: dict[str, int] = {}

    def start(self, waitress: str, platform: Platform, action: str) -> WaitressPresence:
        name = str(waitress).strip()
        if not name:
            raise ValueError("waitress is required")
        presence = WaitressPresence(name, platform, str(action).strip() or "atendiendo", self._clock())
        with self._lock:
            self._active[name.casefold()] = presence
        return presence

    def finish(self, waitress: str) -> None:
        with self._lock:
            self._active.pop(str(waitress).strip().casefold(), None)

    def get(self, waitress: str) -> WaitressPresence | None:
        with self._lock:
            return self._active.get(str(waitress).strip().casefold())

    def reply_for(self, waitress: str) -> PresenceReply:
        presence = self.get(waitress)
        if presence is None:
            return PresenceReply(False, "")
        message = (
            f"Disculpe, cliente-sama. {presence.waitress} se encuentra en "
            f"{presence.platform.capitalize()} atendiendo una mesa en este momento. "
            "Volverá en breve, le informaremos de su pedido."
        )
        return PresenceReply(True, message, presence.platform)

    def route_interaction(
        self,
        waitress: str,
        platform: Platform,
        action: str,
        interaction_id: str,
        *,
        transfer: object | None = None,
    ) -> PresenceReply:
        """Devuelve el aviso de encargado y registra la transferencia si está ocupada."""
        reply = self.reply_for(waitress)
        if reply.occupied:
            self.transfer_interaction(waitress, interaction_id)
            if callable(transfer):
                transfer()
        return reply

    def transfer_interaction(self, waitress: str, interaction_id: str) -> None:
        key = f"{waitress.casefold()}:{interaction_id}"
        with self._lock:
            self._transferred[key] = self._transferred.get(key, 0) + 1

    def transferred_count(self, waitress: str, interaction_id: str) -> int:
        key = f"{str(waitress).strip().casefold()}:{interaction_id}"
        with self._lock:
            return self._transferred.get(key, 0)
