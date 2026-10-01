# -*- coding: utf-8 -*-
"""Telegram membership authorization through python-telegram-bot."""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, ConfigDict


class TelegramMembershipUnavailable(RuntimeError):
    """Telegram membership could not be verified."""


class TelegramMembershipDecision(BaseModel):
    """Normalized authorization result from Telegram ChatMember."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    allowed: bool
    restricted_is_member: bool | None = None


BotFactory = Callable[[str], Any]


def _default_bot_factory(token: str) -> Any:
    from telegram import Bot

    return Bot(token)


class TelegramMembershipVerifier:
    """Calls Bot.get_chat_member and fails closed on dependency errors."""

    ALLOWED_STATUSES = frozenset({"creator", "administrator", "member"})

    def __init__(
        self,
        bot_token: str,
        *,
        bot_factory: BotFactory | None = None,
    ) -> None:
        token = str(bot_token or "").strip()
        if not token:
            raise TelegramMembershipUnavailable("missing_bot_token")
        self._bot_token = token
        self._bot_factory = bot_factory or _default_bot_factory

    @staticmethod
    def _chat_id(value: str) -> int | str:
        clean = str(value).strip()
        if not clean:
            raise ValueError("empty_chat_id")
        try:
            return int(clean)
        except ValueError:
            return clean

    async def check(
        self,
        chat_id: str,
        telegram_user_id: int,
    ) -> TelegramMembershipDecision:
        if int(telegram_user_id) <= 0:
            raise ValueError("invalid_user_id")

        target_chat = self._chat_id(chat_id)
        try:
            bot = self._bot_factory(self._bot_token)
            async with bot:
                member = await bot.get_chat_member(
                    target_chat,
                    int(telegram_user_id),
                )
        except ImportError as error:
            raise TelegramMembershipUnavailable(
                "telegram_dependency_unavailable"
            ) from error
        except TimeoutError as error:
            raise TelegramMembershipUnavailable("telegram_timeout") from error
        except OSError as error:
            raise TelegramMembershipUnavailable(
                "telegram_transport_unavailable"
            ) from error
        except Exception as error:
            error_type = (
                type(error).__module__ + "." + type(error).__name__
            )
            if error_type.startswith("telegram."):
                raise TelegramMembershipUnavailable(
                    "telegram_api_unavailable"
                ) from error
            raise

        status = str(getattr(member, "status", "")).strip().casefold()
        returned_user = getattr(getattr(member, "user", None), "id", None)

        if isinstance(returned_user, bool) or not isinstance(returned_user, int):
            return TelegramMembershipDecision(status=status, allowed=False)
        if returned_user != int(telegram_user_id):
            return TelegramMembershipDecision(status=status, allowed=False)

        if status in self.ALLOWED_STATUSES:
            return TelegramMembershipDecision(status=status, allowed=True)

        if status == "restricted":
            is_member = bool(getattr(member, "is_member", False))
            return TelegramMembershipDecision(
                status=status,
                allowed=is_member,
                restricted_is_member=is_member,
            )

        if status in {"left", "kicked", "banned"}:
            return TelegramMembershipDecision(status=status, allowed=False)

        return TelegramMembershipDecision(status=status, allowed=False)


__all__ = [
    "TelegramMembershipDecision",
    "TelegramMembershipUnavailable",
    "TelegramMembershipVerifier",
]
