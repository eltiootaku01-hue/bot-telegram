from __future__ import annotations

import logging

from aiogram import Bot, F
from aiogram.types import Message

from app.brain.provider import BrainClient, LLMProviderError, LLMRequest
from app.core.config import get_settings
from app.core.identity import BotIdentity
from app.core.module import BotModule

logger = logging.getLogger(__name__)


class BrainChatModule(BotModule):
    """Natural-language chat surface using the configured external LLM."""

    name = "brain_chat"

    def __init__(self, identity: BotIdentity) -> None:
        super().__init__()
        self.identity = identity
        self.brain = BrainClient(get_settings())

    def setup(self) -> None:
        self.router.message.register(self.chat, F.text)

    @staticmethod
    def _directly_addressed(message: Message, bot: Bot) -> bool:
        if message.chat.type == "private":
            return True
        if message.reply_to_message and message.reply_to_message.from_user:
            return message.reply_to_message.from_user.is_bot
        text = message.text or ""
        username = getattr(bot, "_username", "")
        if username and f"@{username.casefold()}" in text.casefold():
            return True
        return text.casefold().strip() in {"bot", "cari", "sunna", "cami", "chie"}

    async def chat(self, message: Message, bot: Bot) -> None:
        if not message.text or not self._directly_addressed(message, bot):
            return
        prompt = message.text.strip()
        if "@" in prompt and prompt.startswith("@"):
            prompt = prompt.split(maxsplit=1)[1] if " " in prompt else ""
        if not prompt:
            prompt = "Decime algo breve y natural para iniciar la conversación."
        try:
            reply = await self.brain.generate(
                LLMRequest(
                    identity=self.identity,
                    user_text=prompt,
                    recent_context=(),
                )
            )
        except LLMProviderError:
            logger.exception("Brain failed for identity=%s", self.identity.value)
            await message.answer("Ahora mismo mi conexión con el cerebro está fallando. Probá de nuevo.")
            return
        await message.answer(reply)
