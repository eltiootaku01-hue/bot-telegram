import asyncio
from datetime import datetime

from aiogram import Bot, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.db.community_models import SetupSession
from app.db.database import Database
from app.db.models import GameAttempt, GameCollection, GameEncounter
from app.db.repositories import MemberRepository
from app.game.catalog import get_character
from app.game.encounter_store import EncounterStore
from app.game.encounters import Encounter, encounter_options
from app.game.engine import GameEngine
from app.game.fusion import fuse_collection
from app.game.progression import apply_capture_progression, collection_status
from app.game.wild_scheduler import WildWaifuScheduler
from app.ui.game_keyboards import combat_keyboard, fusion_keyboard, game_hub_keyboard, gacha_keyboard


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
        self.router.callback_query.register(self.fusion, F.data.startswith("game:fusion:"))
        self.router.callback_query.register(self.combat_action, F.data.startswith("game:combat:"))
        self.router.callback_query.register(self.encounter_answer, F.data.startswith("game:encounter:"))

    async def on_startup(self, bot: Bot) -> None:
        self.wild = WildWaifuScheduler(bot, self.database)
        self.wild.start()

    async def on_shutdown(self) -> None:
        if self.wild is not None:
            await self.wild.stop()
        await super().on_shutdown()

    async def _community_chat_id(self) -> int | None:
        async with self.database.session() as session:
            setup = await session.scalar(
                select(SetupSession.chat_id)
                .where(
                    SetupSession.bot_identity == BotIdentity.CHIE.value,
                    SetupSession.status == "configured",
                )
                .order_by(SetupSession.id.desc())
            )
            return setup

    async def game(self, message: Message) -> None:
        if message.chat.type != "private":
            return
        await message.answer("🎮 <b>Zona de juegos</b>", reply_markup=game_hub_keyboard())

    async def gacha(self, message: Message) -> None:
        if message.chat.type != "private":
            return
        await message.answer("🎰 <b>Gacha de personajes</b>", reply_markup=gacha_keyboard())

    async def inventory_callback(self, callback: CallbackQuery) -> None:
        if callback.message is None:
            await callback.answer("Mensaje no disponible.", show_alert=True)
            return
        chat_id = await self._community_chat_id()
        if chat_id is None:
            await callback.answer("Todavía no hay una comunidad configurada.", show_alert=True)
            return
        await self._show_inventory(callback.message, callback.from_user.id, chat_id)
        await callback.answer()

    async def inventory(self, message: Message) -> None:
        if message.chat.type != "private" or message.from_user is None:
            return
        chat_id = await self._community_chat_id()
        if chat_id is None:
            await message.answer("😰 Chie todavía no configuró la comunidad para el juego.")
            return
        await self._show_inventory(message, message.from_user.id, chat_id)

    async def _show_inventory(self, source: Message, user_id: int, chat_id: int) -> None:
        async with self.database.session() as session:
            profile = await MemberRepository().get_or_create_game_profile(session, user_id, chat_id)
            rows = list(await session.scalars(select(GameCollection).where(GameCollection.profile_id == profile.id)))
        if not rows:
            text = "🎒 <b>Inventario</b>\n\nTodavía no tenés personajes. ¡Salí a cazar una waifu!"
            markup = None
        else:
            lines = [f"🎒 <b>Inventario de {source.from_user.first_name}</b>"]
            evolvable = []
            for item in rows:
                character = get_character(item.character_id)
                progress = collection_status(item)
                lines.append(
                    f"• {character.name} · clase {item.rarity} · Nv.{item.level} · "
                    f"EXP {item.experience} · ×{item.copies} · Evo.{item.evolution_stage}"
                )
                if progress.can_evolve:
                    evolvable.append(item.character_id)
                    lines.append(
                        f"  ↳ ✨ <b>Puede pasar a {progress.next_rarity}</b> "
                        f"(requiere {progress.evolution_copies} copias)"
                    )
            text = "\n".join(lines)
            markup = fusion_keyboard(evolvable[0]) if evolvable else None
        text += "\n\n⏱️ Esta consulta se borra automáticamente en 2 minutos."
        sent = await source.answer(text, reply_markup=markup)
        self.tasks.start(f"delete-inventory-{sent.chat.id}-{sent.message_id}", self._delete_later(sent, 120))

    @staticmethod
    async def _delete_later(message: Message, seconds: int) -> None:
        await asyncio.sleep(seconds)
        try:
            await message.delete()
        except Exception:
            pass

    async def fusion(self, callback: CallbackQuery) -> None:
        character_id = (callback.data or "").split(":", 2)[-1]
        if not character_id or callback.message is None:
            await callback.answer("Fusión inválida.", show_alert=True)
            return
        chat_id = await self._community_chat_id()
        if chat_id is None:
            await callback.answer("Todavía no hay una comunidad configurada.", show_alert=True)
            return
        async with self.database.session() as session:
            profile = await MemberRepository().get_or_create_game_profile(
                session, callback.from_user.id, chat_id
            )
            try:
                result = await fuse_collection(session, profile_id=profile.id, character_id=character_id)
            except ValueError as exc:
                await callback.answer(str(exc), show_alert=True)
                return
            await session.commit()
        character = get_character(character_id)
        await callback.message.edit_text(
            f"✨ <b>{character.name} evolucionó!</b>\n{result.from_rarity} → <b>{result.to_rarity}</b>\n"
            f"Se usaron {result.consumed} copias y quedaron ×{result.remaining}."
        )
        await callback.answer("¡Evolución completada! ✨")

    async def game_hub(self, callback: CallbackQuery) -> None:
        if callback.message is not None:
            await callback.message.edit_text("🎮 <b>Zona de juegos</b>", reply_markup=game_hub_keyboard())
        await callback.answer()

    async def combat(self, message: Message) -> None:
        if message.chat.type != "private":
            return
        await self._show_combat(message)

    async def combat_open(self, callback: CallbackQuery) -> None:
        if callback.message is not None:
            await self._show_combat(callback.message)
        await callback.answer()

    async def _show_combat(self, message: Message) -> None:
        taiga = get_character("taiga")
        await message.answer(
            f"⚔️ <b>{taiga.name}</b> — {taiga.anime}\n\n⚔️ {taiga.attack_name}\n"
            f"🛡️ {taiga.defense_name}\n✨ {taiga.special_name}\n\nElegí una acción.",
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
            now = datetime.utcnow()
            if encounter is None or now >= encounter.expires_at or encounter.status != "active":
                await callback.answer("La waifu ya se fue. 😭", show_alert=True)
                return
            if callback.message.chat.id != encounter.chat_id:
                await callback.answer("Este encuentro pertenece a otra comunidad. 😰", show_alert=True)
                return
            character = get_character(encounter.character_id)
            plan = Encounter(
                id=encounter.id,
                character=character,
                expires_at=encounter.expires_at,
                question=encounter.question,
                answer=encounter.answer,
            )
            options = encounter_options(plan)
            if int(index) >= len(options):
                await callback.answer("Respuesta inválida.", show_alert=True)
                return
            attempt = GameAttempt(
                encounter_id=encounter_id,
                user_id=callback.from_user.id,
                answer=options[int(index)],
                correct=options[int(index)].casefold().strip() == (encounter.answer or "").casefold().strip(),
            )
            session.add(attempt)
            try:
                await session.flush()
            except IntegrityError:
                await session.rollback()
                await callback.answer("Ya intentaste o el evento terminó. 😭", show_alert=True)
                return
            if not attempt.correct:
                await session.commit()
                await callback.answer("❌ Fallaste. Esta oportunidad era solo tuya.", show_alert=True)
                return

            # First correct answer wins. This conditional state transition is the
            # authority: two simultaneous correct callbacks cannot both award rewards.
            claimed = await session.execute(
                update(GameEncounter)
                .where(
                    GameEncounter.id == encounter_id,
                    GameEncounter.status == "active",
                    GameEncounter.expires_at > now,
                )
                .values(status="captured")
            )
            if claimed.rowcount != 1:
                await session.commit()
                await callback.answer("Alguien llegó antes. 😭", show_alert=True)
                return

            profile = await MemberRepository().get_or_create_game_profile(
                session, callback.from_user.id, encounter.chat_id, commit=False
            )
            owned, progress = await apply_capture_progression(
                session,
                profile_id=profile.id,
                user_id=callback.from_user.id,
                chat_id=encounter.chat_id,
                character_id=character.id,
                rarity=encounter.rarity,
            )
            balance = await MemberRepository().add_points(
                session,
                user_id=callback.from_user.id,
                chat_id=encounter.chat_id,
                amount=progress.points_gained,
                reason="Captura de waifu",
                reference_type="encounter",
                reference_id=encounter.id,
                commit=False,
            )
            await session.commit()
        await callback.message.edit_text(
            f"🎉 <b>{callback.from_user.first_name}</b> capturó a {character.name}!\n"
            f"✨ Clase {encounter.rarity} · colección ×{owned.copies}\n⭐ +{progress.points_gained} puntos · saldo: {balance}"
        )
        await callback.answer("¡CAPTURADA! 🎉", show_alert=True)
