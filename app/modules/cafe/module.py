from __future__ import annotations

import hashlib
from html import escape

from aiogram.filters import Command
from aiogram.types import Message

from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.core.time import world_now
from app.db.database import Database
from app.services.world import WorldService


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

    def __init__(self, database: Database, timezone_name: str = "America/Argentina/Buenos_Aires") -> None:
        super().__init__()
        self.database = database
        self.timezone_name = timezone_name
        self.world = WorldService()

    def setup(self) -> None:
        self.router.message.register(self.cafe, Command("cafe"))
        self.router.message.register(self.cafe, Command("menu"))
        self.router.message.register(self.recommendation, Command("recomendacion"))

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
        await message.answer("\n".join(lines))
        await self._observe("cafe_menu", message)

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
