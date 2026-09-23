from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.core.identity import BotIdentity
from app.dialogues.models import DialogueEvent
from app.multibot.filters import BotIdentityFilter


def build_router(*, identity_filter: BotIdentityFilter, vault, dialogues, master_user_id: int = 0) -> Router:
    router = Router(name="multibot_chie")

    @router.message(Command("campana"), identity_filter)
    async def campana(message: Message) -> None:
        await message.answer(
            dialogues.render(
                DialogueEvent.ON_CAMPANA_RUNG,
                "chie",
                {"table_name": "Centro del Café"},
            )
        )

    @router.message(Command("saldo"), identity_filter)
    async def balance(message: Message) -> None:
        if message.from_user is None:
            return
        balance_value = await vault.balance(message.from_user.id)
        await message.answer(
            f"( ಠ_ಠ ) <b>Saldo:</b> {balance_value} Café Coins."
        )

    @router.message(Command("banco"), identity_filter)
    async def bank_admin(message: Message) -> None:
        if message.from_user is None or message.from_user.id != master_user_id:
            await message.answer("( ಠ_ಠ ) Acceso restringido.")
            return
        rows = await vault.lock_status(holder_type="bank", holder_key="main-bank")
        total = sum(int(row.get("available_quantity", 0)) for row in rows)
        await message.answer(
            f"🏦 Banca: {total} cartas disponibles en el pozo."
        )

    return router
