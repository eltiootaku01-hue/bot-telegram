from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.dialogues.models import DialogueEvent
from app.multibot.filters import BotIdentityFilter


def build_router(*, identity_filter: BotIdentityFilter, dialogues) -> Router:
    router = Router(name="multibot_cari")

    @router.message(Command("poker"), identity_filter)
    async def poker(message: Message) -> None:
        text = dialogues.render(
            DialogueEvent.ON_WAIFU_POKER,
            "cari",
        )
        await message.answer(
            f"{text}\n\n♠️ <b>Waifu Poker</b>\n"
            "Las cartas bloqueadas durante una mano no pueden apostarse dos veces. "
            "El motor de manos se mantiene separado de Telegram."
        )

    @router.message(Command("desafio"), identity_filter)
    async def challenge(message: Message) -> None:
        target = message.text.partition(" ")[2].strip() if message.text else ""
        label = target or "alguien de la mesa"
        await message.answer(
            f"🎯 Desafío para {label}.\n"
            "La resolución de la mano y las transferencias deben pasar por la Bóveda."
        )

    return router
