from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def rare_approval_keyboard(approval_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Aprobar", callback_data=f"admin:rare:approve:{approval_id}"),
                InlineKeyboardButton(text="❌ Rechazar", callback_data=f"admin:rare:reject:{approval_id}"),
            ]
        ]
    )
