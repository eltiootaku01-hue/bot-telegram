from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def chie_start_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🚀 Empezar a trabajar", callback_data="chie:setup:start"))
    return builder.as_markup()


def chie_setup_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📌 Ya me agregaste de admin", callback_data="chie:setup:check"))
    builder.row(InlineKeyboardButton(text="❌ Cancelar", callback_data="chie:setup:cancel"))
    return builder.as_markup()


def command_hub_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👋 Comunidad", callback_data="chie:hub:community"),
        InlineKeyboardButton(text="🎮 Juegos", callback_data="chie:hub:games"),
    )
    builder.row(
        InlineKeyboardButton(text="📰 Contenido", callback_data="chie:hub:content"),
        InlineKeyboardButton(text="💰 Puntos", callback_data="chie:hub:points"),
    )
    builder.row(InlineKeyboardButton(text="🎨 Pedir imagen", callback_data="chie:request:start"))
    builder.row(InlineKeyboardButton(text="⚙️ Configuración", callback_data="chie:hub:config"))
    return builder.as_markup()


def chie_request_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Cancelar pedido", callback_data="chie:request:cancel"))
    return builder.as_markup()
