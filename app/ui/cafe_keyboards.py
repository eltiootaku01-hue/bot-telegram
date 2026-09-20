from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.config import Settings
from app.core.identity import BotIdentity


def cafe_menu_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    """Show only configured cross-bot links; Cari stays usable without them."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🍿 Recomendación",
            callback_data="cafe:recommendation",
        ),
        InlineKeyboardButton(
            text="🕵️ Misterio",
            callback_data="cafe:mystery:open",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="☀️ Evento del Café",
            callback_data="cafe:event:open",
        ),
        InlineKeyboardButton(
            text="🌤️ Momento",
            callback_data="cafe:context:open",
        ),
    )

    links = (
        (BotIdentity.SUNNA, "🎮 Abrir Sunna"),
        (BotIdentity.CAMI, "📚 Abrir Cami"),
        (BotIdentity.CHIE, "📋 Abrir Chie"),
    )
    for identity, label in links:
        url = settings.link_for(identity.value).strip()
        if url:
            builder.row(InlineKeyboardButton(text=label, url=url))

    return builder.as_markup()
