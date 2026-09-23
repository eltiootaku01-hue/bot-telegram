from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.dialogues.models import DialogueEvent
from app.multibot.filters import BotIdentityFilter


def build_router(
    *,
    identity_filter: BotIdentityFilter,
    vault,
    dialogues,
    bank_key: str,
) -> Router:
    router = Router(name="multibot_sunna")

    @router.message(Command("roll"), identity_filter)
    async def roll(message: Message) -> None:
        user = message.from_user
        if user is None:
            return
        items = await vault.bank_inventory(bank_key)
        available = [item for item in items if int(item.get("available_quantity", 0)) > 0]
        if not available:
            await message.answer("*(ಠ_ಠ)* La Banca no tiene cartas disponibles ahora.")
            return

        # Selection happens locally; transfer remains authoritative in the Vault.
        import secrets

        chosen = secrets.choice(available)
        idempotency_key = f"multibot-roll:{message.chat.id}:{message.message_id}"
        result = None
        for _attempt in range(3):
            try:
                result = await vault.transfer(
                    card_id=str(chosen["card_id"]),
                    from_type="bank",
                    from_key=bank_key,
                    to_type="user",
                    to_key=str(user.id),
                    quantity=1,
                    actor_user_id=user.id,
                    idempotency_key=idempotency_key,
                )
                break
            except RuntimeError:
                refreshed = await vault.bank_inventory(bank_key)
                available = [
                    item for item in refreshed
                    if int(item.get("available_quantity", 0)) > 0
                ]
                if not available:
                    await message.answer("( ಠ_ಠ ) La Banca se quedó sin cartas disponibles.")
                    return
                chosen = secrets.choice(available)
        if result is None:
            await message.answer("( ಠ_ಠ ) La Banca cambió mientras intentaba entregar tu carta.")
            return
        card_code = next(
            (str(item.get("card_code", "")) for item in available if item["card_id"] == chosen["card_id"]),
            "",
        )
        card_label = card_code or str(chosen["card_id"])
        text = dialogues.render(
            DialogueEvent.ON_CARD_ROLL,
            "sunna",
            {"card_name": card_label},
        )
        await message.answer(text)
        await message.answer(f"🎴 {card_label} · +1 carta")

    @router.callback_query(F.data.startswith("claim:"), identity_filter)
    async def claim(callback: CallbackQuery) -> None:
        if callback.message is None or callback.from_user is None:
            await callback.answer("Reclamo inválido.", show_alert=True)
            return
        card_id = (callback.data or "").removeprefix("claim:")
        if not card_id or ":" in card_id:
            await callback.answer("Carta inválida.", show_alert=True)
            return
        result = await vault.transfer(
            card_id=card_id,
            from_type="bank",
            from_key=bank_key,
            to_type="user",
            to_key=str(callback.from_user.id),
            quantity=1,
            actor_user_id=callback.from_user.id,
            idempotency_key=f"multibot-claim:{callback.message.chat.id}:{callback.id}",
        )
        await callback.answer(
            f"🎴 Carta reclamada · transacción #{result.get('transaction_id', '?')}",
            show_alert=True,
        )

    return router
