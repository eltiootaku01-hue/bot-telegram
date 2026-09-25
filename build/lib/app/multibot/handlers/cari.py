from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.multibot.filters import BotIdentityFilter
from app.multibot.conversation.engine import ConversationEngine


def build_router(*, identity_filter: BotIdentityFilter, dialogues, vault, conversation: ConversationEngine) -> Router:
    router = Router(name="multibot_cari")

    @router.message(Command("poker"), identity_filter)
    async def poker(message: Message) -> None:
        if message.from_user is None:
            return
        text = conversation.handle(
            identity="cari",
            user_id=message.from_user.id,
            text="poker",
            user_name=message.from_user.full_name,
        )
        locked = await vault.lock_status(holder_key=str(message.from_user.id))
        await message.answer(
            f"{text}\n\n♠️ <b>Waifu Poker</b>\n"
            f"Tenés {sum(int(row.get('available_quantity', 0)) for row in locked)} cartas disponibles y "
            f"{sum(int(row.get('locked_quantity', 0)) for row in locked)} bloqueadas.\n"
            "El motor de manos se mantiene separado de Telegram."
        )

    @router.message(Command("desafio", "challenge"), identity_filter)
    async def challenge(message: Message) -> None:
        if message.from_user is None:
            return
        text = conversation.handle(
            identity="cari",
            user_id=message.from_user.id,
            text="challenge",
            user_name=message.from_user.full_name,
        )
        target = message.text.partition(" ")[2].strip() if message.text else ""
        label = target or "alguien de la mesa"
        await message.answer(
            f"{text}\n\n🎯 Desafío para {label}.\n"
            "La resolución de la mano y las transferencias deben pasar por la Bóveda."
        )

    @router.message(identity_filter)
    async def intent_handler(message: Message) -> None:
        if message.from_user is None:
            return
        # Deterministic parser + FSM + local template engine; no AI and no network I/O.
        text = conversation.handle(
            identity="cari",
            user_id=message.from_user.id,
            text=message.text,
            user_name=message.from_user.full_name,
        )
        await message.answer(text)

    return router
