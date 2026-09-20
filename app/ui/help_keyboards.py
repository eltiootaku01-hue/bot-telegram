from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.identity import BotIdentity


def help_keyboard(identity: BotIdentity, section: str = "home") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if section == "home":
        rows: dict[BotIdentity, tuple[tuple[str, str], ...]] = {
            BotIdentity.CARI: (
                ("☕ Café", "cafe"),
                ("🍿 Recomendación", "recommendation"),
                ("💬 Conversación", "conversation"),
                ("🛡️ Moderación", "moderation"),
            ),
            BotIdentity.SUNNA: (
                ("🎮 Juegos", "games"),
                ("🎰 Gacha", "gacha"),
                ("🎒 Inventario", "inventory"),
                ("💰 Puntos", "points"),
            ),
            BotIdentity.CAMI: (
                ("📚 Catálogo", "catalog"),
                ("📖 Anime", "anime"),
                ("🔁 Recuperación", "recovery"),
                ("📊 Archivo", "archive"),
            ),
            BotIdentity.CHIE: (
                ("⚙️ Configurar", "configure"),
                ("📌 Comandos", "commands"),
                ("📜 Reglas", "rules"),
                ("🌍 Mundo", "world"),
            ),
        }
        for label, key in rows[identity]:
            builder.row(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"help:{identity.value}:{key}",
                )
            )
    else:
        builder.row(
            InlineKeyboardButton(
                text="⬅️ Ayuda principal",
                callback_data=f"help:{identity.value}:home",
            )
        )

    return builder.as_markup()
