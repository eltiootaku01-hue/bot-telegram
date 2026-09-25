from __future__ import annotations

import asyncio
from typing import Any, Mapping

from aiogram import Bot
from aiogram.enums import ChatAction
from aiogram.types import FSInputFile, Message

from app.command_center.models import ManualMessageCommand, TemporaryMessagePolicy
from app.dialogues.models import DialogueEvent
from app.dialogues.renderer import DialogueRenderer
from app.dialogues.store import DialogueStore


class TelegramGateway:
    """Small, testable Telegram Bot API adapter used by Casa de Comando."""

    def __init__(
        self,
        bots: dict[str, Bot],
        *,
        dialogues: DialogueStore | None = None,
    ) -> None:
        self._bots = bots
        self._temporary_policy = TemporaryMessagePolicy()
        self._dialogues = dialogues
        self._dialogue_renderer = DialogueRenderer(dialogues) if dialogues is not None else None

    def bot_for(self, identity: str) -> Bot:
        try:
            return self._bots[identity.casefold()]
        except KeyError as exc:
            raise ValueError(f"Telegram bot identity not configured: {identity}") from exc

    async def typing(self, identity: str, chat_id: int) -> bool:
        await self.bot_for(identity).send_chat_action(chat_id, ChatAction.TYPING)
        return True

    async def send_text(
        self,
        command: ManualMessageCommand,
    ) -> Message:
        kwargs: dict[str, Any] = {}
        if command.message_thread_id is not None:
            kwargs["message_thread_id"] = command.message_thread_id
        if command.protect_content:
            kwargs["protect_content"] = True
        return await self.bot_for(command.identity).send_message(
            command.chat_id,
            command.text,
            **kwargs,
        )

    async def send_dialogue(
        self,
        *,
        event: DialogueEvent | str,
        identity: str,
        chat_id: int,
        message_thread_id: int | None = None,
        variables: Mapping[str, object] | None = None,
        temporary: bool = True,
    ) -> Message:
        if self._dialogue_renderer is None:
            raise RuntimeError("TelegramGateway has no DialogueStore configured")
        text = self._dialogue_renderer.render(event, identity, variables)
        command = ManualMessageCommand(
            identity=identity,
            chat_id=chat_id,
            message_thread_id=message_thread_id,
            text=text,
        )
        await self.typing(identity, chat_id)
        if temporary:
            return await self.send_temporary(command)
        return await self.send_text(command)

    async def send_card(
        self,
        *,
        identity: str,
        chat_id: int,
        asset_path: str,
        caption: str,
        message_thread_id: int | None = None,
        protected: bool = True,
    ) -> Message:
        kwargs: dict[str, Any] = {
            "caption": caption,
            "protect_content": protected,
        }
        if message_thread_id is not None:
            kwargs["message_thread_id"] = message_thread_id
        return await self.bot_for(identity).send_photo(
            chat_id=chat_id,
            photo=FSInputFile(asset_path),
            **kwargs,
        )

    async def send_temporary(
        self,
        command: ManualMessageCommand,
    ) -> Message:
        message = await self.send_text(command)
        delay = self._temporary_policy.delay_for(command.text)
        asyncio.create_task(self._delete_after(command.identity, message, delay))
        return message

    async def _delete_after(self, identity: str, message: Message, delay: float) -> None:
        await asyncio.sleep(delay)
        try:
            await self.bot_for(identity).delete_message(message.chat.id, message.message_id)
        except Exception:
            return
