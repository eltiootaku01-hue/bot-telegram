from __future__ import annotations

import hashlib
from html import escape

from aiogram import F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.core.identity import BotIdentity
from app.core.config import Settings
from app.core.module import BotModule
from app.core.time import world_now
from app.db.database import Database
from app.services.cafe_mystery import CAFE_MYSTERIES, mystery_for
from app.services.world import WorldService
from app.ui.cafe_keyboards import cafe_menu_keyboard


CAFE_MENU: tuple[tuple[str, str], ...] = (
    ("☕ Café y bebidas", "Jugos, café y una mesa tranquila para quedarse un rato."),
    ("📚 Anime y manga", "Cari puede charlar y derivar consultas al personaje adecuado."),
    ("🎮 Zona de juegos", "Sunna mantiene la zona de juegos y WaifuMon."),
    ("📦 Archivo y publicaciones", "Cami mantiene el material y las publicaciones."),
    ("📋 Recepción y reglas", "Chie organiza avisos, permisos y coordinación."),
    ("🕵️ Misterio diario", "Cada día el Café Otaku tiene un caso pequeño para resolver."),
    ("🎨 Pedidos", "La comunidad puede usar puntos para solicitar material mediante Chie."),
)


DAILY_RECOMMENDATIONS: tuple[tuple[str, str], ...] = (
    ("Sword Art Online", "Una opción para una sesión de acción y aventura."),
    ("Frieren", "Una opción para una sesión tranquila y contemplativa."),
    ("SPY x FAMILY", "Una opción ligera para compartir en grupo."),
    ("Kaguya-sama: Love Is War", "Una opción para una tarde de comedia y juegos."),
    ("Violet Evergarden", "Una opción para una sesión más emotiva."),
)


class CafeModule(BotModule):
    """Deterministic Café Otaku host surface owned by Cari."""

    name = "cafe"

    def __init__(
        self,
        database: Database,
        timezone_name: str = "America/Argentina/Buenos_Aires",
        settings: Settings | None = None,
    ) -> None:
        super().__init__()
        self.database = database
        self.settings = settings or Settings(bot_world_timezone=timezone_name)
        self.timezone_name = self.settings.bot_world_timezone
        self.world = WorldService()

    def setup(self) -> None:
        self.router.message.register(self.cafe, Command("cafe"))
        self.router.message.register(self.cafe, Command("menu"))
        self.router.message.register(self.recommendation, Command("recomendacion"))
        self.router.message.register(self.mystery, Command("misterio"))
        self.router.callback_query.register(
            self.recommendation_callback,
            F.data == "cafe:recommendation",
        )
        self.router.callback_query.register(
            self.mystery_open_callback,
            F.data == "cafe:mystery:open",
        )
        self.router.callback_query.register(
            self.mystery_callback,
            F.data.startswith("cafe:mystery:"),
        )

    async def _observe(self, action_key: str, message: Message) -> None:
        if message.from_user is None:
            return
        try:
            async with self.database.session() as session:
                await self.world.observe_action(
                    session,
                    bot_identity=BotIdentity.CARI,
                    action_key=action_key,
                    user_id=message.from_user.id,
                    chat_id=message.chat.id,
                )
        except Exception:
            # World telemetry is intentionally non-critical to the user-facing path.
            return

    async def cafe(self, message: Message) -> None:
        lines = [
            "☕ <b>Café Otaku</b>",
            "",
            "Bienvenido. Este es el punto de encuentro de Ciudad Animals.",
            "",
            "<b>Disponible ahora:</b>",
        ]
        lines.extend(f"• <b>{escape(name)}</b> — {escape(description)}" for name, description in CAFE_MENU)
        lines.extend(
            (
                "",
                "🎀 Podés usar <code>/recomendacion</code> para pedir una recomendación del día.",
                "🎮 Los juegos y WaifuMon se abren desde Sunna.",
                "📚 El archivo de material se consulta con Cami.",
            )
        )
        await message.answer(
            "\n".join(lines),
            reply_markup=cafe_menu_keyboard(self.settings),
        )
        await self._observe("cafe_menu", message)

    async def recommendation_callback(self, callback: CallbackQuery) -> None:
        if callback.message is None or callback.from_user is None:
            await callback.answer("No pude abrir la recomendación.", show_alert=True)
            return
        await self.recommendation(callback.message)
        await callback.answer()


    async def mystery_open_callback(self, callback: CallbackQuery) -> None:
        if callback.message is None:
            await callback.answer("No pude abrir el misterio.", show_alert=True)
            return
        await self.mystery(callback.message)
        await callback.answer()

    async def mystery_callback(self, callback: CallbackQuery) -> None:
        if callback.message is None or callback.from_user is None:
            await callback.answer("No pude abrir el misterio.", show_alert=True)
            return
        parts = (callback.data or "").split(":")
        if len(parts) != 4 or not parts[2].isdigit() or not parts[3].isdigit():
            await callback.answer("Misterio inválido.", show_alert=True)
            return

        case_index = int(parts[2])
        option_index = int(parts[3])
        day_key = world_now(self.timezone_name).date().isoformat()
        mystery = mystery_for(day_key, callback.message.chat.id)
        current_case_index = CAFE_MYSTERIES.index(mystery)

        if case_index != current_case_index:
            await callback.answer(
                "Este misterio ya venció. Abrí /misterio para el caso de hoy.",
                show_alert=True,
            )
            return
        if option_index < 0 or option_index >= len(mystery.options):
            await callback.answer("Opción inválida.", show_alert=True)
            return

        if option_index == mystery.answer_index:
            await callback.answer("¡Correcto! 🔎", show_alert=True)
            await callback.message.edit_text(
                f"🕵️ <b>{escape(mystery.title)}</b>\n\n"
                f"✅ <b>Correcto.</b> {escape(mystery.reveal)}\n\n"
                "Este es un caso cotidiano del Café; no modifica el canon de la historia."
            )
            await self._observe("mystery_solved", callback.message)
            return

        await callback.answer("No. Revisá las pistas. 👀", show_alert=True)

    async def mystery(self, message: Message) -> None:
        day_key = world_now(self.timezone_name).date().isoformat()
        mystery = mystery_for(day_key, message.chat.id)
        case_index = CAFE_MYSTERIES.index(mystery)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{chr(65 + index)}. {option}",
                        callback_data=f"cafe:mystery:{case_index}:{index}",
                    )
                ]
                for index, option in enumerate(mystery.options)
            ]
        )
        await message.answer(
            f"🕵️ <b>Misterio del Café — {escape(mystery.title)}</b>\n\n"
            f"{escape(mystery.question)}\n\n"
            "Elegí una opción. Este minicaso es cotidiano y no añade hechos al canon.",
            reply_markup=keyboard,
        )
        await self._observe("mystery_open", message)

    async def recommendation(self, message: Message) -> None:
        day_key = world_now(self.timezone_name).date().isoformat()
        digest = hashlib.sha256(f"{day_key}:{message.chat.id}".encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % len(DAILY_RECOMMENDATIONS)
        title, description = DAILY_RECOMMENDATIONS[index]
        await message.answer(
            "☕ <b>Recomendación de Cari</b>\n\n"
            f"🎬 <b>{escape(title)}</b>\n"
            f"{escape(description)}\n\n"
            "Sin spoilers y sin cambiar el catálogo del proyecto."
        )
        await self._observe("daily_recommendation", message)
