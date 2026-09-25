from __future__ import annotations
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from app.multibot.filters import BotIdentityFilter
from app.multibot.conversation.engine import ConversationEngine

def build_router(*, identity_filter: BotIdentityFilter, vault, dialogues, bank_key: str, conversation: ConversationEngine) -> Router:
    router = Router(name="multibot_sunna")

    @router.message(Command("roll"), identity_filter)
    async def roll(message: Message) -> None:
        if message.from_user is None: return
        conversation.handle(identity="sunna", user_id=message.from_user.id, text="roll", user_name=message.from_user.full_name)
        try:
            items = await vault.bank_inventory(bank_key)
            available = [item for item in items if int(item.get("available_quantity", 0)) > 0]
            if not available:
                await message.answer("(ಠ_ಠ) La Banca no tiene cartas disponibles ahora."); return
            import secrets
            chosen = secrets.choice(available)
            result = await vault.transfer(card_id=str(chosen["card_id"]), from_type="bank", from_key=bank_key, to_type="user", to_key=str(message.from_user.id), quantity=1, actor_user_id=message.from_user.id, idempotency_key=f"multibot-roll:{message.chat.id}:{message.message_id}")
            card_code = str(chosen.get("card_code") or chosen["card_id"])
            await message.answer(dialogues.render("ON_CARD_ROLL", "sunna", {"card_name": card_code}))
            await message.answer(f"🎴 {card_code} · +1 carta")
        except RuntimeError:
            await message.answer("( ಠ_ಠ ) La Banca cambió mientras intentaba entregar tu carta.")
        finally:
            conversation.state.release("sunna", message.from_user.id)

    @router.callback_query(F.data.startswith("claim:"), identity_filter)
    async def claim(callback: CallbackQuery) -> None:
        if callback.message is None or callback.from_user is None:
            await callback.answer("Reclamo inválido.", show_alert=True); return
        card_id = (callback.data or "").removeprefix("claim:")
        if not card_id or ":" in card_id:
            await callback.answer("Carta inválida.", show_alert=True); return
        conversation.handle(identity="sunna", user_id=callback.from_user.id, text="claim", user_name=callback.from_user.full_name)
        try:
            result = await vault.transfer(card_id=card_id, from_type="bank", from_key=bank_key, to_type="user", to_key=str(callback.from_user.id), quantity=1, actor_user_id=callback.from_user.id, idempotency_key=f"multibot-claim:{callback.message.chat.id}:{callback.id}")
            await callback.answer(f"🎴 Carta reclamada · transacción #{result.get('transaction_id', '?')}", show_alert=True)
        finally:
            conversation.state.release("sunna", callback.from_user.id)
    return router
