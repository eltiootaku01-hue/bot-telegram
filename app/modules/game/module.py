import asyncio
from datetime import datetime

from aiogram import Bot, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.core.module import BotModule
from app.db.database import Database
from app.db.models import GameCollection
from app.db.repositories import MemberRepository
from app.game.catalog import get_character
from app.game.encounter_store import EncounterStore
from app.game.engine import GameEngine
from app.game.progression import capture_reward, collection_status
from app.game.wild_scheduler import WildWaifuScheduler
from app.ui.game_keyboards import combat_keyboard, game_hub_keyboard, gacha_keyboard


class GameModule(BotModule):
    name = "game"

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.engine = GameEngine()
        self.encounters = EncounterStore()
        self.wild: WildWaifuScheduler | None = None

    def setup(self) -> None:
        self.router.message.register(self.game, Command("juego"))
        self.router.message.register(self.gacha, Command("gacha"))
        self.router.message.register(self.inventory, Command("inventario"))
        self.router.message.register(self.combat, Command("combate"))
        self.router.callback_query.register(self.game_hub, F.data == "game:gacha:open")
        self.router.callback_query.register(self.inventory_callback, F.data == "game:inventory:open")
        self.router.callback_query.register(self.combat_open, F.data == "game:combat:open")
        self.router.callback_query.register(self.gacha_roll, F.data == "game:gacha:roll")
        self.router.callback_query.register(self.combat_action, F.data.startswith("game:combat:"))
        self.router.callback_query.register(self.encounter_answer, F.data.startswith("game:encounter:"))

    async def on_startup(self, bot: Bot) -> None:
        self.wild = WildWaifuScheduler(bot, self.database)
        self.wild.start()

    async def on_shutdown(self) -> None:
        if self.wild is not None:
            await self.wild.stop()

    async def game(self, message: Message) -> None:
        await message.answer("🎮 <b>Zona de juegos</b>", reply_markup=game_hub_keyboard())

    async def gacha(self, message: Message) -> None:
        await message.answer(
            "🎰 <b>Gacha de personajes</b>\n\nLas ilustraciones y rarezas crecerán por niveles.",
            reply_markup=gacha_keyboard(),
        )

    async def inventory_callback(self, callback: CallbackQuery) -> None:
        if callback.message is None:
            await callback.answer("Mensaje no disponible.", show_alert=True)
            return
        await self._show_inventory(callback.message, callback.from_user.id, callback.message.chat.id)
        await callback.answer()

    async def inventory(self, message: Message) -> None:
        if message.from_user is None:
            return
        await self._show_inventory(message, message.from_user.id, message.chat.id)

    async def _show_inventory(self, source: Message, user_id: int, chat_id: int) -> None:
        async with self.database.session() as session:
            profile = await MemberRepository().get_or_create_game_profile(session, user_id, chat_id)
            rows = list(await session.scalars(select(GameCollection).where(GameCollection.profile_id == profile.id)))
        if not rows:
            text = "🎒 <b>Inventario</b>\n\nTodavía no tenés personajes. ¡Salí a cazar una waifu!"
        else:
            lines = [f"🎒 <b>Inventario de {source.from_user.first_name}</b>"]
            for item in rows:
                character = get_character(item.character_id)
                progress = collection_status(item)
                lines.append(
                    f"• {character.name} · clase {item.rarity} · Nv.{item.level} · "
                    f"EXP {item.experience} · ×{item.copies} · Evo.{item.evolution_stage}"
                )
                if progress.can_evolve:
                    lines.append("  ↳ ✨ <b>Lista para evolucionar</b>")
            lines.append("\n⏱️ Esta consulta se borra automáticamente en 2 minutos.")
            text = "\n".join(lines)
        sent = await source.answer(text)
        asyncio.create_task(self._delete_later(sent, 120))

    @staticmethod
    async def _delete_later(message: Message, seconds: int) -> None:
        await asyncio.sleep(seconds)
        try:
            await message.delete()
        except Exception:
            pass

    async def game_hub(self, callback: CallbackQuery) -> None:
        if callback.message is not None:
            await callback.message.edit_text("🎮 <b>Zona de juegos</b>", reply_markup=game_hub_keyboard())
        await callback.answer()

    async def combat(self, message: Message) -> None:
        await self._show_combat(message)

    async def combat_open(self, callback: CallbackQuery) -> None:
        if callback.message is not None:
            await self._show_combat(callback.message)
        await callback.answer()

    async def _show_combat(self, message: Message) -> None:
        taiga = get_character("taiga")
        await message.answer(
            f"⚔️ <b>{taiga.name}</b> — {taiga.anime}\n\n"
            f"⚔️ {taiga.attack_name}\n🛡️ {taiga.defense_name}\n✨ {taiga.special_name}\n\nElegí una acción.",
            reply_markup=combat_keyboard(),
        )

    async def gacha_roll(self, callback: CallbackQuery) -> None:
        rarity = self.engine.roll_gacha(seed=str(callback.id))
        await callback.answer(f"¡Salió {rarity.value}!", show_alert=True)

    async def combat_action(self, callback: CallbackQuery) -> None:
        action_key = callback.data.rsplit(":", 1)[-1]
        if action_key not in self.engine.ACTIONS:
            await callback.answer("Acción inválida.", show_alert=True)
            return
        taiga = get_character("taiga")
        result = self.engine.combat(taiga, taiga, action_key, callback.id)
        critical = " 💥 CRÍTICO" if result.critical else ""
        await callback.answer(f"{result.action.label}: {result.damage} daño{critical}", show_alert=True)

    async def encounter_answer(self, callback: CallbackQuery) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) != 5 or parts[0] != "game" or parts[1] != "encounter" or parts[3] != "answer":
            await callback.answer("Evento inválido.", show_alert=True)
            return
        encounter_id, index = parts[2], parts[4]
        if callback.message is None or not index.isdigit():
            await callback.answer("Respuesta inválida.", show_alert=True)
            return
        async with self.database.session() as session:
            encounter = await self.encounters.get(session, encounter_id)
            if encounter is None or datetime.utcnow() >= encounter.expires_at:
                await callback.answer("La waifu ya se fue. 😭", show_alert=True)
                return
            character = get_character(encounter.character_id)
            options = ["ryuuji", "kitamura", "ami"] if encounter.question else [character.name.lower()]
            if int(index) >= len(options):
                await callback.answer("Respuesta inválida.", show_alert=True)
                return
            result = await self.encounters.claim_attempt(
                session, encounter_id, callback.from_user.id, options[int(index)]
            )
            if result is None:
                await callback.answer("Ya intentaste o el evento terminó. 😭", show_alert=True)
                return
            if not result:
                await callback.answer("❌ Fallaste. Esta oportunidad era solo tuya.", show_alert=True)
                return
            profile = await MemberRepository().get_or_create_game_profile(
                session, callback.from_user.id, encounter.chat_id
            )
            owned = await session.scalar(
                select(GameCollection).where(
                    GameCollection.profile_id == profile.id,
                    GameCollection.character_id == character.id,
                )
            )
            if owned is None:
                owned = GameCollection(
                    profile_id=profile.id, character_id=character.id, rarity=encounter.rarity
                )
                session.add(owned)
            else:
                owned.copies += 1
            capture_reward(profile, owned)
            encounter.status = "captured"
            await session.commit()
        await callback.message.edit_text(
            f"🎉 <b>{callback.from_user.first_name}</b> capturó a {character.name}!\n"
            f"✨ Clase {encounter.rarity} · ahora forma parte de su colección."
        )
        await callback.answer("¡CAPTURADA! 🎉", show_alert=True)
