from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from app.core.identity import BotIdentity
from app.db.card_vault_models import BotState
from app.db.database import Database
from app.dialogues.models import DialogueEvent
from app.multibot.filters import BotIdentityFilter
from app.multibot.conversation.engine import ConversationEngine


def build_router(
    *,
    identity_filter: BotIdentityFilter,
    vault,
    dialogues,
    database: Database,
    master_user_id: int = 0,
    conversation: ConversationEngine,
    bank_key: str = "main-bank",
) -> Router:
    router = Router(name="multibot_chie")

    @router.message(Command("campana"), identity_filter)
    async def campana(message: Message) -> None:
        if message.from_user is None:
            return
        gate = conversation.handle(identity="chie", user_id=message.from_user.id, text="campana", user_name=message.from_user.full_name, cooldown_seconds=5)
        if gate.startswith("(") and "cooldown" in gate.casefold():
            await message.answer(gate)
            return
        table_name = "Centro del Café"
        statuses: list[str] = []
        async with database.session() as session:
            rows = list(
                await session.scalars(
                    select(BotState).order_by(BotState.bot_identity)
                )
            )
        for row in rows:
            if row.bot_identity == BotIdentity.CHIE.value:
                continue
            location = row.table_key or row.zone_key or "fuera de escena"
            state = row.status or "idle"
            statuses.append(f"• {row.bot_identity.title()}: {state} · {location}")

        if statuses:
            table_name = ", ".join(
                row.table_key for row in rows if row.table_key
            ) or table_name

        dialogue = dialogues.render(
            DialogueEvent.ON_CAMPANA_RUNG,
            "chie",
            {"table_name": table_name},
        )
        text = dialogue
        if statuses:
            text += "\n\n<b>Estado actual</b>\n" + "\n".join(statuses[:4])
        await message.answer(f"{gate}\n\n{text}")

    @router.message(Command("saldo"), identity_filter)
    async def balance(message: Message) -> None:
        if message.chat.type != "private" or message.from_user is None:
            return
        balance_value = await vault.balance(message.from_user.id)
        await message.answer(
            f"( ಠ_ಠ ) <b>Saldo:</b> {balance_value} Café Coins."
        )

    @router.message(Command("banco"), identity_filter)
    async def bank_admin(message: Message) -> None:
        if message.chat.type != "private":
            return
        if message.from_user is None or message.from_user.id != master_user_id:
            await message.answer("( ಠ_ಠ ) Acceso restringido.")
            return
        rows = await vault.lock_status(holder_type="bank", holder_key=bank_key)
        total = sum(int(row.get("available_quantity", 0)) for row in rows)
        locked = sum(int(row.get("locked_quantity", 0)) for row in rows)
        await message.answer(
            f"🏦 <b>Banca</b> · disponibles: {total} · bloqueadas: {locked}"
        )

    @router.message(identity_filter)
    async def intent_handler(message: Message) -> None:
        if message.from_user is None: return
        await message.answer(conversation.handle(identity="chie", user_id=message.from_user.id, text=message.text, user_name=message.from_user.full_name))

    return router
