from __future__ import annotations

import logging
import re

from aiogram import F
from aiogram.types import Message

from app.brain.provider import BrainClient, LLMProviderError, LLMRequest
from app.core.config import Settings, get_settings
from app.core.identity import BotIdentity, get_profile
from app.core.module import BotModule

logger = logging.getLogger(__name__)


class BrainChatModule(BotModule):
    """Optional natural-language chat surface backed by a configured LLM."""

    name = "brain_chat"

    def __init__(self, identity: BotIdentity, settings: Settings | None = None) -> None:
        super().__init__()
        self.identity = identity
        self.settings = settings or get_settings()
        self.brain = BrainClient(self.settings)

    def setup(self) -> None:
        self.router.message.register(self.chat, F.text)

    def _directly_addressed(self, message: Message) -> bool:
        """Only treat this bot's own name, the generic 'bot', or its own reply as addressed."""
        if message.chat.type == "private":
            return True

        reply = message.reply_to_message
        current_bot = getattr(message, "bot", None)
        if reply is not None and reply.from_user is not None:
            if not reply.from_user.is_bot:
                reply = None
            elif current_bot is not None and reply.from_user.id == current_bot.id:
                return True
            else:
                return False

        text = (message.text or "").casefold().strip()
        display_name = get_profile(self.identity).display_name.casefold()
        if text == "bot" or text == display_name:
            return True
        return bool(re.match(rf"^{re.escape(display_name)}(?:[,:;!?]|\s|$)", text))

    async def chat(self, message: Message) -> None:
        # AI is an enhancement, never a dependency for the deterministic bot modules.
        if not self.settings.ai_for(self.identity):
            return
        if not message.text or not self._directly_addressed(message):
            return
        prompt = message.text.strip()
        normalized = prompt.casefold().strip("!?.,:;")
        if normalized in {"bot", get_profile(self.identity).display_name.casefold()}:
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
