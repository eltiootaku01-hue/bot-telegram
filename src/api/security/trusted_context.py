# -*- coding: utf-8 -*-
"""Trusted Mini App Room context using the existing Telegram room registry."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from bot_ia.interfaces.telegram_room_routing import TelegramRoomRouter


REFERENCE_PATTERN = re.compile(r"^tctx_[A-Za-z0-9_-]{43}$")
BOT_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{5,32}$")
MIN_CONTEXT_SECRET_CHARS = 32


class TrustedContextError(ValueError):
    """Error seguro de Trusted Context."""


class TrustedContextConfigurationError(RuntimeError):
    """Configuración ausente o inválida de Trusted Context."""


class TrustedCafeContext(BaseModel):
    """Proyección server-side del contexto de un Room Telegram."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference: str
    issuer: str
    chat_id: str
    message_thread_id: int = Field(ge=0)
    room_key: str
    reusable: bool = True


class TrustedContextRegistry:
    """Emite referencias opacas derivadas de rutas Telegram registradas."""

    def __init__(
        self,
        router: TelegramRoomRouter,
        secret: str,
        *,
        issuer: str = "cafe-otaku",
    ) -> None:
        clean_secret = str(secret).strip()
        clean_issuer = str(issuer).strip()
        if len(clean_secret) < MIN_CONTEXT_SECRET_CHARS:
            raise TrustedContextConfigurationError("invalid_context_secret")
        if not clean_issuer:
            raise TrustedContextConfigurationError("missing_context_issuer")
        self._router = router
        self._secret = clean_secret.encode("utf-8")
        self._issuer = clean_issuer

    def _canonical_payload(
        self,
        chat_id: str,
        message_thread_id: int,
        room_key: str,
    ) -> bytes:
        return (
            f"{self._issuer}\x1f{chat_id}\x1f{message_thread_id}\x1f{room_key}"
        ).encode("utf-8")

    def _reference_for(
        self,
        chat_id: str,
        message_thread_id: int,
        room_key: str,
    ) -> str:
        digest = hmac.new(
            self._secret,
            self._canonical_payload(chat_id, message_thread_id, room_key),
            hashlib.sha256,
        ).digest()
        encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return f"tctx_{encoded}"

    def issue(
        self,
        chat_id: str,
        message_thread_id: int,
    ) -> TrustedCafeContext:
        clean_chat = str(chat_id).strip()
        try:
            thread_id = int(message_thread_id)
        except (TypeError, ValueError) as error:
            raise TrustedContextError("invalid_room_identity") from error
        if not clean_chat or thread_id < 0:
            raise TrustedContextError("invalid_room_identity")

        try:
            room_key = self._router.resolve(clean_chat, thread_id)
        except Exception as error:
            raise TrustedContextError("room_routing_unavailable") from error
        if not room_key:
            raise TrustedContextError("unknown_room")

        reference = self._reference_for(clean_chat, thread_id, str(room_key))
        return TrustedCafeContext(
            reference=reference,
            issuer=self._issuer,
            chat_id=clean_chat,
            message_thread_id=thread_id,
            room_key=str(room_key),
        )

    def resolve(self, reference: str) -> TrustedCafeContext:
        value = str(reference or "").strip()
        if not REFERENCE_PATTERN.fullmatch(value):
            raise TrustedContextError("invalid_context_reference")

        try:
            routes = self._router.list_routes()
        except Exception as error:
            raise TrustedContextError("room_routing_unavailable") from error

        for route in routes:
            candidate = self._reference_for(
                route.chat_id,
                route.message_thread_id,
                route.room_key,
            )
            if hmac.compare_digest(candidate, value):
                return TrustedCafeContext(
                    reference=value,
                    issuer=self._issuer,
                    chat_id=route.chat_id,
                    message_thread_id=route.message_thread_id,
                    room_key=route.room_key,
                )

        raise TrustedContextError("unknown_context_reference")


def build_main_mini_app_link(
    bot_username: str,
    context_reference: str,
) -> str:
    """Construye el launcher W01-C: Main Mini App + startapp."""
    username = str(bot_username or "").strip().lstrip("@")
    if not BOT_USERNAME_PATTERN.fullmatch(username):
        raise TrustedContextError("invalid_bot_username")
    reference = str(context_reference or "").strip()
    if not REFERENCE_PATTERN.fullmatch(reference):
        raise TrustedContextError("invalid_context_reference")
    return f"https://t.me/{username}?startapp={quote(reference, safe='')}"


def build_configured_registry(
    router: TelegramRoomRouter,
) -> TrustedContextRegistry:
    secret = os.getenv("TMA_CONTEXT_SECRET", "").strip()
    issuer = os.getenv("TMA_CONTEXT_ISSUER", "cafe-otaku").strip()
    return TrustedContextRegistry(router, secret, issuer=issuer)


__all__ = [
    "REFERENCE_PATTERN",
    "TrustedCafeContext",
    "TrustedContextConfigurationError",
    "TrustedContextError",
    "TrustedContextRegistry",
    "build_configured_registry",
    "build_main_mini_app_link",
]
