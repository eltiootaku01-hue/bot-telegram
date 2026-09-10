from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def game_hub_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎲 Gacha", callback_data="game:gacha:open"),
        InlineKeyboardButton(text="🎒 Inventario", callback_data="game:inventory:open"),
    )
    builder.row(InlineKeyboardButton(text="⚔️ Combate", callback_data="game:combat:open"))
    builder.row(InlineKeyboardButton(text="🧠 Trivia", callback_data="game:trivia:start"))
    return builder.as_markup()


def combat_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚔️ Ataque", callback_data="game:combat:attack"),
        InlineKeyboardButton(text="🛡️ Defensa", callback_data="game:combat:defend"),
    )
    builder.row(InlineKeyboardButton(text="✨ Especial", callback_data="game:combat:special"))
    return builder.as_markup()


def gacha_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎲 Tirar gacha", callback_data="game:gacha:roll"))
    builder.row(InlineKeyboardButton(text="🎒 Inventario", callback_data="game:inventory:open"))
    return builder.as_markup()


def encounter_keyboard(encounter_id: str, options: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, option in enumerate(options):
        builder.add(InlineKeyboardButton(
            text=option,
            callback_data=f"game:encounter:{encounter_id}:answer:{index}",
        ))
    builder.adjust(2)
    return builder.as_markup()


def trivia_keyboard(round_id: int, options: tuple[str, ...]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, option in enumerate(options):
        builder.add(InlineKeyboardButton(
            text=option,
            callback_data=f"game:trivia:{round_id}:{index}",
        ))
    builder.adjust(2)
    return builder.as_markup()
