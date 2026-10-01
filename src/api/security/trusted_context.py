# -*- coding: utf-8 -*-
"""Trusted Mini App Room context backed by an opaque server-side registry."""

from __future__ import annotations

import os
from pathlib import Path
import re
import secrets
import time
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from bot_ia.interfaces.telegram_room_routing import TelegramRoomRouter
from bot_ia.paths import PROJECT_ROOT


REFERENCE_PREFIX = "tctx_"
REFERENCE_PATTERN = re.compile(r"^tctx_[A-Za-z0-9_-]{43}$")
BOT_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{5,32}$")
DEFAULT_CONTEXT_MAX_AGE_SECONDS = 3600
MAX_ISSUE_ATTEMPTS = 8


class TrustedContextError(ValueError):
    """Safe trusted-context resolution error."""


class TrustedContextConfigurationError(RuntimeError):
    """Trusted-context configuration is missing or invalid."""


class TrustedCafeContext(BaseModel):
    """Server-side authorization context for one Telegram Room."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference: str
    issuer: str
    chat_id: str
    message_thread_id: int = Field(ge=0)
    room_key: str
    issued_at: int = Field(gt=0)
    expires_at: int = Field(gt=0)
    revoked_at: int | None = Field(default=None, gt=0)
    reusable: bool = True


class _StoredTrustedContext(BaseModel):
    """Persisted registry record; clients never control this structure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference: str
    issuer: str
    chat_id: str
    message_thread_id: int = Field(ge=0)
    room_key: str
    issued_at: int = Field(gt=0)
    expires_at: int = Field(gt=0)
    revoked_at: int | None = Field(default=None, gt=0)
    reusable: bool = True


def _configured_max_age(value: int | None) -> int:
    if value is not None:
        try:
            result = int(value)
        except (TypeError, ValueError) as error:
            raise TrustedContextConfigurationError(
                "invalid_context_max_age"
            ) from error
    else:
        raw = os.getenv(
            "TMA_CONTEXT_MAX_AGE_SECONDS",
            str(DEFAULT_CONTEXT_MAX_AGE_SECONDS),
        ).strip()
        try:
            result = int(raw)
        except ValueError as error:
            raise TrustedContextConfigurationError(
                "invalid_context_max_age"
            ) from error
    if result < 1:
        raise TrustedContextConfigurationError("invalid_context_max_age")
    return result


class TrustedContextRegistry:
    """Issue, resolve and revoke opaque Room references."""

    def __init__(
        self,
        router: TelegramRoomRouter,
        *,
        issuer: str = "cafe-otaku",
        store_dir: str | Path | None = None,
        max_age_seconds: int | None = None,
        token_factory=secrets.token_urlsafe,
    ) -> None:
        clean_issuer = str(issuer).strip()
        if not clean_issuer:
            raise TrustedContextConfigurationError("missing_context_issuer")
        self._router = router
        self._issuer = clean_issuer
        self._store_dir = (
            Path(store_dir).expanduser().resolve()
            if store_dir is not None
            else PROJECT_ROOT / "config" / "tma_trusted_contexts"
        )
        try:
            self._store_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise TrustedContextConfigurationError(
                "context_store_unavailable"
            ) from error
        self._max_age_seconds = _configured_max_age(max_age_seconds)
        self._token_factory = token_factory

    def _path_for(self, reference: str) -> Path:
        value = str(reference or "").strip()
        if not REFERENCE_PATTERN.fullmatch(value):
            raise TrustedContextError("invalid_context_reference")
        return self._store_dir / f"{value}.json"

    @staticmethod
    def _now(now: float | None) -> int:
        current = time.time() if now is None else float(now)
        if current <= 0:
            raise TrustedContextError("invalid_context_time")
        return int(current)

    def _load(self, reference: str) -> _StoredTrustedContext:
        path = self._path_for(reference)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise TrustedContextError("unknown_context_reference") from error
        except OSError as error:
            raise TrustedContextError("context_store_unavailable") from error
        try:
            return _StoredTrustedContext.model_validate_json(raw)
        except ValueError as error:
            raise TrustedContextError("invalid_context_record") from error

    def issue(
        self,
        chat_id: str,
        message_thread_id: int,
        *,
        now: float | None = None,
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

        issued_at = self._now(now)
        expires_at = issued_at + self._max_age_seconds

        for _ in range(MAX_ISSUE_ATTEMPTS):
            reference = REFERENCE_PREFIX + str(
                self._token_factory(32)
            ).strip()
            if not REFERENCE_PATTERN.fullmatch(reference):
                continue

            record = _StoredTrustedContext(
                reference=reference,
                issuer=self._issuer,
                chat_id=clean_chat,
                message_thread_id=thread_id,
                room_key=str(room_key),
                issued_at=issued_at,
                expires_at=expires_at,
                reusable=True,
            )
            path = self._path_for(reference)
            try:
                with path.open("x", encoding="utf-8") as handle:
                    handle.write(record.model_dump_json() + "\n")
            except FileExistsError:
                continue
            except OSError as error:
                raise TrustedContextError(
                    "context_store_unavailable"
                ) from error

            return TrustedCafeContext.model_validate(
                record.model_dump()
            )

        raise TrustedContextError("context_reference_collision")

    def resolve(
        self,
        reference: str,
        *,
        now: float | None = None,
    ) -> TrustedCafeContext:
        record = self._load(reference)
        if record.issuer != self._issuer:
            raise TrustedContextError("foreign_context_issuer")

        current = self._now(now)
        if record.revoked_at is not None:
            raise TrustedContextError("revoked_context_reference")
        if current >= record.expires_at:
            raise TrustedContextError("expired_context_reference")

        try:
            current_room_key = self._router.resolve(
                record.chat_id,
                record.message_thread_id,
            )
        except Exception as error:
            raise TrustedContextError("room_routing_unavailable") from error

        if not current_room_key:
            raise TrustedContextError("unknown_room")
        if str(current_room_key) != record.room_key:
            raise TrustedContextError("room_route_changed")

        return TrustedCafeContext.model_validate(
            record.model_dump()
        )

    def revoke(
        self,
        reference: str,
        *,
        now: float | None = None,
    ) -> TrustedCafeContext:
        record = self._load(reference)
        if record.issuer != self._issuer:
            raise TrustedContextError("foreign_context_issuer")

        revoked_at = record.revoked_at or self._now(now)
        updated = record.model_copy(update={"revoked_at": revoked_at})
        path = self._path_for(reference)
        temporary = path.with_suffix(".json.tmp")

        try:
            temporary.write_text(
                updated.model_dump_json() + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, path)
        except OSError as error:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise TrustedContextError(
                "context_store_unavailable"
            ) from error

        return TrustedCafeContext.model_validate(
            updated.model_dump()
        )


def build_main_mini_app_link(
    bot_username: str,
    context_reference: str,
) -> str:
    """Build the W01-C Main Mini App launcher with startapp."""
    username = str(bot_username or "").strip().lstrip("@")
    if not BOT_USERNAME_PATTERN.fullmatch(username):
        raise TrustedContextError("invalid_bot_username")
    reference = str(context_reference or "").strip()
    if not REFERENCE_PATTERN.fullmatch(reference):
        raise TrustedContextError("invalid_context_reference")
    return f"https://t.me/{username}?startapp={quote(reference, safe='')}"


def issue_main_mini_app_link(
    registry: TrustedContextRegistry,
    bot_username: str,
    chat_id: str,
    message_thread_id: int,
    *,
    now: float | None = None,
) -> tuple[TrustedCafeContext, str]:
    """Register one Room context and build its Main Mini App link."""
    context = registry.issue(
        chat_id,
        message_thread_id,
        now=now,
    )
    return context, build_main_mini_app_link(
        bot_username,
        context.reference,
    )


def build_configured_registry(
    router: TelegramRoomRouter,
) -> TrustedContextRegistry:
    return TrustedContextRegistry(
        router,
        issuer=os.getenv(
            "TMA_CONTEXT_ISSUER",
            "cafe-otaku",
        ).strip(),
    )


__all__ = [
    "DEFAULT_CONTEXT_MAX_AGE_SECONDS",
    "REFERENCE_PATTERN",
    "TrustedCafeContext",
    "TrustedContextConfigurationError",
    "TrustedContextError",
    "TrustedContextRegistry",
    "build_configured_registry",
    "build_main_mini_app_link",
    "issue_main_mini_app_link",
]
