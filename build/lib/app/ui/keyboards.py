from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🧠 Hablar", callback_data="menu:chat"),
        InlineKeyboardButton(text="🎮 Juegos", callback_data="menu:games"),
    )
    builder.row(
        InlineKeyboardButton(text="📚 Biblioteca", callback_data="menu:library"),
        InlineKeyboardButton(text="🖼️ Imágenes", callback_data="menu:images"),
    )
    builder.row(
        InlineKeyboardButton(text="👥 Comunidad", callback_data="menu:community"),
        InlineKeyboardButton(text="⚙️ Configuración", callback_data="menu:settings"),
    )
    return builder.as_markup()


def section_menu(section: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    labels = {
        "chat": ("💬 Nueva conversación", "chat:new"),
        "games": ("🎲 Próximamente: juegos", "games:soon"),
        "library": ("🔎 Buscar", "library:search"),
        "images": ("🖼️ Explorar", "images:browse"),
        "community": ("📊 Comunidad", "community:stats"),
        "settings": ("🎭 Personalidad", "settings:personality"),
    }
    text, callback = labels.get(section, ("⬅️ Volver", "menu:home"))
    builder.row(InlineKeyboardButton(text=text, callback_data=callback))
    builder.row(InlineKeyboardButton(text="⬅️ Menú principal", callback_data="menu:home"))
    return builder.as_markup()
