# -*- coding: utf-8 -*-
"""Intervención directa Schrödinger para operaciones administrativas multiplataforma."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Callable


@dataclass(frozen=True, slots=True)
class LiveTarget:
    platform: str
    chat_id: str
    title: str = ""


class SchrodingerError(RuntimeError):
    """Error controlado del canal de intervención directa."""


class SchrodingerRouter:
    """Router deliberadamente pequeño: GUI decide el destino, este módulo valida y despacha."""

    PLATFORM_TELEGRAM = "telegram"
    PLATFORM_DISCORD = "discord"

    def __init__(
        self,
        *,
        telegram_sender: Callable[[str, str, str | None], object] | None = None,
        discord_sender: Callable[[str, str, str | None], object] | None = None,
        moderation_action: Callable[[str, str, str], object] | None = None,
    ) -> None:
        self.telegram_sender = telegram_sender
        self.discord_sender = discord_sender
        self.moderation_action = moderation_action

    @staticmethod
    def token() -> str:
        token = os.getenv("SCHRODINGER_BOT_TOKEN", "").strip()
        if not token:
            raise SchrodingerError("SCHRODINGER_BOT_TOKEN no está configurado")
        return token

    @classmethod
    def from_environment(cls) -> "SchrodingerRouter":
        return cls()

    @staticmethod
    def validate_target(target: LiveTarget) -> LiveTarget:
        platform = target.platform.strip().casefold()
        if platform not in {"telegram", "discord"}:
            raise SchrodingerError("Plataforma no soportada")
        chat_id = target.chat_id.strip()
        if not chat_id:
            raise SchrodingerError("El chat/canal no puede estar vacío")
        return LiveTarget(platform, chat_id, target.title.strip())

    def send_text(self, target: LiveTarget, text: str, media: str | None = None) -> object:
        target = self.validate_target(target)
        text = text.strip()
        if not text and not media:
            raise SchrodingerError("El mensaje no puede estar vacío")
        sender = (
            self.telegram_sender
            if target.platform == self.PLATFORM_TELEGRAM
            else self.discord_sender
        )
        if sender is None:
            raise SchrodingerError(
                f"No existe un adaptador conectado para {target.platform}"
            )
        return sender(target.chat_id, text, media)

    def moderate(self, action: str, guild_id: str, user_id: str) -> object:
        action = action.strip().casefold()
        if action not in {"unmute", "kick", "ban"}:
            raise SchrodingerError("Acción administrativa no soportada")
        if self.moderation_action is None:
            raise SchrodingerError("No existe un adaptador de moderación conectado")
        return self.moderation_action(action, guild_id.strip(), user_id.strip())


def build_schrodinger_token_hint() -> str:
    """Texto de configuración para .env; nunca devuelve el secreto."""
    return "SCHRODINGER_BOT_TOKEN=" + ("configured" if os.getenv("SCHRODINGER_BOT_TOKEN") else "")
