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
        self.router.message.register(self.combat, Command("combate"))
        self.router.callback_query.register(self.game_hub, F.data == "game:gacha:open")
        self.router.callback_query.register(self.collection, F.data == "game:collection:open")
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

    async def game_hub(self, callback: CallbackQuery) -> None:
        await callback.message.edit_text("🎮 <b>Zona de juegos</b>", reply_markup=game_hub_keyboard())
        await callback.answer()

    async def collection(self, callback: CallbackQuery) -> None:
        await callback.answer("📖 Colección persistente: interfaz en construcción.")

    async def gacha_roll(self, callback: CallbackQuery) -> None:
        rarity = self.engine.roll_gacha(seed=str(callback.id))
        await callback.answer(f"¡Salió {rarity.value.upper()}!", show_alert=True)

    async def combat(self, message: Message) -> None:
        await self._show_combat(message)

    async def combat_open(self, callback: CallbackQuery) -> None:
        await self._show_combat(callback.message)
        await callback.answer()

    async def _show_combat(self, message: Message) -> None:
        taiga = get_character("taiga")
        await message.answer(
            f"⚔️ <b>{taiga.name}</b> — {taiga.anime}\n\n"
            f"⚔️ {taiga.attack_name}\n🛡️ {taiga.defense_name}\n✨ {taiga.special_name}\n\n"
            "Elegí una acción.",
            reply_markup=combat_keyboard(),
        )

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
        options = ["ryuuji", "kitamura", "ami"]
        if index not in {"0", "1", "2"} or callback.message is None:
            await callback.answer("Respuesta inválida.", show_alert=True)
            return

        async with self.database.sessions() as session:
            encounter = await self.encounters.get(session, encounter_id)
            if encounter is None:
                await callback.answer("La waifu ya se fue. 😭", show_alert=True)
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
            character = get_character(encounter.character_id)
            owned = await session.scalar(
                select(GameCollection).where(
                    GameCollection.profile_id == profile.id,
                    GameCollection.character_id == character.id,
                )
            )
            if owned is None:
                session.add(GameCollection(profile_id=profile.id, character_id=character.id, rarity=encounter.rarity))
            else:
                owned.copies += 1
            encounter.status = "captured"
            await session.commit()

        await callback.message.edit_text(
            f"🎉 <b>{callback.from_user.first_name}</b> capturó a {character.name}!\n"
            f"✨ Clase {encounter.rarity} · ahora forma parte de su colección."
        )
        await callback.answer("¡CAPTURADA! 🎉", show_alert=True)
