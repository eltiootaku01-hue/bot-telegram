from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def cami_media_actions(asset_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏷️ Ponerle tag", callback_data=f"cami:media:tag:{asset_id}"),
        InlineKeyboardButton(text="🗓️ Programar envío", callback_data=f"cami:media:schedule:{asset_id}"),
    )
    builder.row(InlineKeyboardButton(text="📨 Asociar a pedido", callback_data=f"cami:media:request:{asset_id}"))
    builder.row(InlineKeyboardButton(text="📦 Archivar", callback_data=f"cami:media:archive:{asset_id}"))
    return builder.as_markup()


def cami_pending_requests(asset_id: int, requests: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for request_id, label in requests:
        builder.row(
            InlineKeyboardButton(
                text=label[:40],
                callback_data=f"cami:req:link:{asset_id}:{request_id}",
            )
        )
    return builder.as_markup()


def cami_publish_destination(asset_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🌐 Página + tema del grupo", callback_data=f"cami:media:dest:both:{asset_id}"),
    )
    builder.row(InlineKeyboardButton(text="💬 Solo tema del grupo", callback_data=f"cami:media:dest:group:{asset_id}"))
    builder.row(InlineKeyboardButton(text="↩️ Cancelar", callback_data=f"cami:media:cancel:{asset_id}"))
    return builder.as_markup()


def cami_publication_recovery(asset_id: int) -> InlineKeyboardMarkup:
    """Explicit human decision for a Telegram send whose result is unknown."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Confirmar publicado", callback_data=f"cami:recovery:confirm:{asset_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔁 Reintentar envío", callback_data=f"cami:recovery:retry:{asset_id}"),
        InlineKeyboardButton(text="📦 Descartar", callback_data=f"cami:recovery:discard:{asset_id}"),
    )
    return builder.as_markup()
