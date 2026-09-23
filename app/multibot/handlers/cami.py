from __future__ import annotations

from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.multibot.filters import BotIdentityFilter


def build_router(*, identity_filter: BotIdentityFilter, vault) -> Router:
    router = Router(name="multibot_cami")

    @router.message(Command("inventario"), identity_filter)
    async def inventory(message: Message) -> None:
        if message.from_user is None:
            return
        rows = await vault.inventory(message.from_user.id)
        if not rows:
            await message.answer("📚 Tu inventario está vacío.")
            return
        lines = ["📚 <b>Inventario de Cami</b>", ""]
        for row in rows[:25]:
            code = escape(str(row.get("card_code") or row.get("card_id")))
            quantity = int(row.get("quantity", 0))
            locked = int(row.get("locked_quantity", 0))
            lines.append(f"• <b>{code}</b> ×{quantity} · 🔒 {locked}")
        await message.answer("\n".join(lines))

    @router.message(Command("catalogo"), identity_filter)
    async def catalog(message: Message) -> None:
        cards = await vault.catalog()
        if not cards:
            await message.answer("📚 El catálogo todavía está vacío.")
            return
        lines = ["📚 <b>Catálogo de la Bóveda</b>", ""]
        for card in cards[:30]:
            lines.append(
                f"• <b>{escape(str(card.get('card_code') or card.get('id')))}</b> "
                f"· {escape(str(card.get('character_name') or 'Sin nombre'))} "
                f"· {escape(str(card.get('rarity') or 'C'))}"
            )
        await message.answer("\n".join(lines))

    return router
