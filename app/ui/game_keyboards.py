from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def combat_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚔️ Ataque", callback_data="game:combat:attack"),
        InlineKeyboardButton(text="🛡️ Defensa", callback_data="game:combat:defend"),
    )
    builder.row(
        InlineKeyboardButton(text="✨ Especial", callback_data="game:combat:special")
    )
    return builder.as_markup()


def gacha_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎲 Tirar gacha", callback_data="game:gacha:roll"))
    return builder.as_markup()
