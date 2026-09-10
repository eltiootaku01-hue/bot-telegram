from aiogram import F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.core.module import BotModule
from app.ui.keyboards import main_menu, section_menu


class SystemModule(BotModule):
    name = "system"

    def setup(self) -> None:
        self.router.message.register(self.start, CommandStart())
        self.router.message.register(self.ping, F.text.casefold() == "ping")
        self.router.callback_query.register(self.menu_callback, F.data.startswith("menu:"))
        self.router.callback_query.register(self.section_callback)

    async def start(self, message: Message) -> None:
        await message.answer(
            "👋 Bienvenido.\n\n"
            "Este bot se está construyendo como una plataforma modular. "
            "Usa los botones para explorar sus funciones sin depender de una lista enorme de comandos.",
            reply_markup=main_menu(),
        )

    async def ping(self, message: Message) -> None:
        await message.answer("pong")

    async def menu_callback(self, callback: CallbackQuery) -> None:
        data = callback.data or "menu:home"
        if data == "menu:home":
            await callback.message.edit_text(
                "🏠 <b>Menú principal</b>\n\nElige qué quieres hacer:",
                reply_markup=main_menu(),
            )
        else:
            section = data.removeprefix("menu:")
            names = {
                "chat": "🧠 Conversación",
                "games": "🎮 Juegos",
                "library": "📚 Biblioteca",
                "images": "🖼️ Imágenes",
                "community": "👥 Comunidad",
                "settings": "⚙️ Configuración",
            }
            await callback.message.edit_text(
                f"<b>{names.get(section, 'Sección')}</b>\n\n"
                "La interfaz está preparada; esta sección se conectará a su módulo correspondiente.",
                reply_markup=section_menu(section),
            )
        await callback.answer()

    async def section_callback(self, callback: CallbackQuery) -> None:
        await callback.answer("Módulo en construcción", show_alert=False)
