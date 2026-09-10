from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def cami_media_actions(asset_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏷️ Ponerle tag", callback_data=f"cami:media:tag:{asset_id}"),
        InlineKeyboardButton(text="🗓️ Programar envío", callback_data=f"cami:media:schedule:{asset_id}"),
    )
    builder.row(InlineKeyboardButton(text="📦 Archivar", callback_data=f"cami:media:archive:{asset_id}"))
    return builder.as_markup()


def cami_publish_destination(asset_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🌐 Página + tema del grupo", callback_data=f"cami:media:dest:both:{asset_id}"),
    )
    builder.row(InlineKeyboardButton(text="💬 Solo tema del grupo", callback_data=f"cami:media:dest:group:{asset_id}"))
    builder.row(InlineKeyboardButton(text="↩️ Cancelar", callback_data=f"cami:media:cancel:{asset_id}"))
    return builder.as_markup()
