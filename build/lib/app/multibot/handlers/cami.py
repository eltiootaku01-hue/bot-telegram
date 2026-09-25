from __future__ import annotations
from html import escape
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from app.multibot.filters import BotIdentityFilter
from app.multibot.conversation.engine import ConversationEngine

def build_router(*, identity_filter: BotIdentityFilter, vault, conversation: ConversationEngine) -> Router:
    router = Router(name="multibot_cami")
    @router.message(Command("inventario"), identity_filter)
    async def inventory(message: Message) -> None:
        if message.from_user is None: return
        conversation.handle(identity="cami", user_id=message.from_user.id, text="inventario", user_name=message.from_user.full_name)
        try:
            rows = await vault.inventory(message.from_user.id)
            if not rows: await message.answer("📚 Tu inventario está vacío."); return
            lines=["📚 <b>Inventario de Cami</b>",""]
            for row in rows[:25]:
                code=escape(str(row.get("card_code") or row.get("card_id"))); lines.append(f"• <b>{code}</b> ×{int(row.get('quantity',0))} · 🔒 {int(row.get('locked_quantity',0))}")
            await message.answer("\n".join(lines))
        finally: conversation.state.release("cami", message.from_user.id)
    @router.message(Command("catalogo"), identity_filter)
    async def catalog(message: Message) -> None:
        if message.from_user is None: return
        conversation.handle(identity="cami", user_id=message.from_user.id, text="catalogo", user_name=message.from_user.full_name)
        try:
            cards=await vault.catalog()
            if not cards: await message.answer("📚 El catálogo todavía está vacío."); return
            lines=["📚 <b>Catálogo de la Bóveda</b>",""]
            for card in cards[:30]:
                lines.append(f"• <b>{escape(str(card.get('card_code') or card.get('id')))}</b> · {escape(str(card.get('character_name') or 'Sin nombre'))} · {escape(str(card.get('rarity') or 'C'))}")
            await message.answer("\n".join(lines))
        finally: conversation.state.release("cami", message.from_user.id)
    @router.message(identity_filter)
    async def intent_handler(message: Message) -> None:
        if message.from_user is None: return
        await message.answer(conversation.handle(identity="cami", user_id=message.from_user.id, text=message.text, user_name=message.from_user.full_name))
    return router
