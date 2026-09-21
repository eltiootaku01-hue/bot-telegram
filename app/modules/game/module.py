import asyncio
import logging

from aiogram import Bot, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, Message
from sqlalchemy import func, select

from app.characters.director import CharacterDirector
from app.characters.models import CharacterIntent
from app.core.assets import resolve_asset
from app.core.config import Settings, get_settings
from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.db.database import Database
from app.db.models import GameCardCollection, GameCollection, GameItemInventory, GameProfile
from app.db.repositories import MemberRepository
from app.game.card_service import CardCollectionService
from app.game.catalog import get_character
from app.game.encounter_store import EncounterAttemptResult, EncounterStore
from app.game.encounters import Encounter, encounter_options
from app.game.engine import GameEngine
from app.game.fusion import fuse_collection
from app.game.gacha import GACHA_COST_POINTS, GachaService
from app.game.missions import DailyMissionService
from app.game.progression import apply_capture_progression, collection_status
from app.game.waifu_art import art_candidates_for
from app.game.waifu_browser import (
    WaifuFilter,
    WaifuFilterField,
    page_for,
    render_detail,
    render_page,
)
from app.game.wild_scheduler import WildWaifuScheduler
from app.game.waifu_detector import WaifuDetectorService
from app.game.waifu_gift_scheduler import WaifuGiftScheduler
from app.game.waifu_gifts import WaifuGiftService
from app.services.community import CommunityResolver
from app.services.world import WorldService
from app.ui.control_keyboards import rare_approval_keyboard
from app.ui.game_keyboards import (
    combat_keyboard,
    fusion_keyboard,
    game_hub_keyboard,
    gacha_keyboard,
    waifu_catalog_detail_keyboard,
    waifu_catalog_keyboard,
    waifu_filter_categories_keyboard,
    waifu_filter_options_keyboard,
    detector_keyboard,
    item_consume_keyboard,
    item_inventory_keyboard,
    encounter_keyboard,
    cards_keyboard,
)

logger = logging.getLogger(__name__)


class GameModule(BotModule):
    name = "game"

    def __init__(self, database: Database, settings: Settings | None = None) -> None:
        super().__init__()
        self.database = database
        self.settings = settings or get_settings()
        self.engine = GameEngine()
        self.gacha_service = GachaService(self.engine)
        self.missions = DailyMissionService()
        self.encounters = EncounterStore()
        self.detector_service = WaifuDetectorService()
        self.gift_service = WaifuGiftService()
        self.gift_scheduler: WaifuGiftScheduler | None = None
        self.wild: WildWaifuScheduler | None = None
        self.world = WorldService()
        self.community = CommunityResolver(self.settings)
        self.characters = CharacterDirector()
        self.card_service = CardCollectionService()
        self._card_selection: dict[int, int] = {}

    def setup(self) -> None:
        self.router.message.register(self.game, Command("juego"))
        self.router.message.register(self.gacha, Command("gacha"))
        self.router.message.register(self.inventory, Command("inventario"))
        self.router.message.register(self.combat, Command("combate"))
        self.router.message.register(self.missions_command, Command("misiones"))
        self.router.message.register(self.waifus, Command("waifus"))
        self.router.message.register(self.detector, Command("detector"))
        self.router.message.register(self.items, Command("objetos"))
        self.router.message.register(self.cards, Command("cartas"))
        self.router.callback_query.register(self.gacha_open, F.data == "game:gacha:open")
        self.router.callback_query.register(self.inventory_callback, F.data == "game:inventory:open")
        self.router.callback_query.register(self.combat_open, F.data == "game:combat:open")
        self.router.callback_query.register(self.missions_open, F.data == "game:missions:open")
        self.router.callback_query.register(self.detector_open, F.data == "game:detector:open")
        self.router.callback_query.register(self.detector_fight, F.data.startswith("game:detector:fight:"))
        self.router.callback_query.register(self.gift_claim, F.data.startswith("game:gift:claim:"))
        self.router.callback_query.register(self.item_choose, F.data.startswith("game:item:choose:"))
        self.router.callback_query.register(self.item_absorb, F.data.startswith("game:item:absorb:"))
        self.router.callback_query.register(self.cards_page, F.data.startswith("game:cards:page:"))
        self.router.callback_query.register(self.card_pick, F.data.startswith("game:card:pick:"))
        self.router.callback_query.register(self.gacha_roll, F.data == "game:gacha:roll")
        self.router.callback_query.register(self.fusion, F.data.startswith("game:fusion:"))
        self.router.callback_query.register(self.combat_action, F.data.startswith("game:combat:"))
        self.router.callback_query.register(self.encounter_answer, F.data.startswith("game:encounter:"))
        self.router.callback_query.register(self.waifu_detail, F.data.startswith("game:waifu:d:"))
        self.router.callback_query.register(self.waifu_catalog_filters, F.data == "game:waifus:filters")
        self.router.callback_query.register(self.waifu_catalog_filter_options, F.data.startswith("game:waifus:filter:"))
        self.router.callback_query.register(self.waifu_catalog_filter_set, F.data.startswith("game:waifus:set:"))
        self.router.callback_query.register(self.waifu_catalog_clear_filter, F.data == "game:waifus:clear")
        self.router.callback_query.register(self.waifu_catalog_page, F.data.startswith("game:waifus:page:"))

    async def on_startup(self, bot: Bot) -> None:
        self.wild = WildWaifuScheduler(bot, self.database, settings=self.settings)
        self.wild.start()
        self.gift_scheduler = WaifuGiftScheduler(
            bot,
            self.database,
            settings=self.settings,
        )
        self.gift_scheduler.start()

    async def on_shutdown(self) -> None:
        if self.gift_scheduler is not None:
            await self.gift_scheduler.stop()
        if self.wild is not None:
            await self.wild.stop()
        await super().on_shutdown()

    async def _observe_action(
        self,
        action_key: str,
        user_id: int,
        chat_id: int | None = None,
    ) -> None:
        """Record world usage outside the gameplay transaction."""
        try:
            async with self.database.session() as session:
                await self.world.observe_action(
                    session,
                    bot_identity=BotIdentity.SUNNA,
                    action_key=action_key,
                    user_id=user_id,
                    chat_id=chat_id,
                )
        except Exception:
            logger.exception("World observation failed for Sunna action=%s user=%s", action_key, user_id)

    def _game_reaction(self, intent: CharacterIntent, roll: int) -> str:
        response = self.characters.choose(BotIdentity.SUNNA, intent, roll=roll)
        return response.scene.text if response is not None else ""

    def _mission_day_key(self) -> str:
        return self.missions.day_key(
            timezone_name=self.settings.bot_world_timezone,
        )

    async def _record_mission(
        self,
        session,
        *,
        user_id: int,
        chat_id: int,
        mission_key: str,
        reference_type: str,
        reference_id: str,
    ) -> tuple[bool, int, int, int]:
        day_key = self._mission_day_key()
        progress = await self.missions.record(
            session,
            user_id=user_id,
            chat_id=chat_id,
            day_key=day_key,
            mission_key=mission_key,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        claimed, balance = await self.missions.claim(
            session,
            user_id=user_id,
            chat_id=chat_id,
            day_key=day_key,
            mission_key=mission_key,
        )
        return claimed, balance, progress.progress, progress.target

    async def cards(self, message: Message) -> None:
        if message.chat.type != "private" or message.from_user is None:
            return
        chat_id = await self._community_chat_id(message.from_user.id)
        if chat_id is None:
            await message.answer("😰 Todavía no hay una comunidad asociada.")
            return
        await self._show_cards(message, message.from_user.id, chat_id, 1)

    async def cards_page(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer(
                "Este panel solo funciona en tu chat privado con Sunna. 😰",
                show_alert=True,
            )
            return
        parts = (callback.data or "").split(":")
        if len(parts) != 4 or not parts[3].isdigit() or callback.message is None:
            await callback.answer("Página de cartas inválida.", show_alert=True)
            return
        chat_id = await self._community_chat_id(callback.from_user.id)
        if chat_id is None:
            await callback.answer("No hay una comunidad configurada.", show_alert=True)
            return
        await self._show_cards(callback.message, callback.from_user.id, chat_id, int(parts[3]))
        await callback.answer()

    async def _show_cards(
        self,
        source: Message,
        user_id: int,
        chat_id: int,
        page: int,
    ) -> None:
        page_size = 8
        async with self.database.session() as session:
            profile = await session.scalar(
                select(GameProfile).where(
                    GameProfile.user_id == user_id,
                    GameProfile.chat_id == chat_id,
                )
            )
            if profile is None:
                rows = []
                total = 0
            else:
                total = await session.scalar(
                    select(func.count(GameCardCollection.id)).where(
                        GameCardCollection.profile_id == profile.id,
                        GameCardCollection.copies > 0,
                    )
                )
                rows = list(
                    await session.scalars(
                        select(GameCardCollection)
                        .where(
                            GameCardCollection.profile_id == profile.id,
                            GameCardCollection.copies > 0,
                        )
                        .order_by(GameCardCollection.id.asc())
                        .offset(max(0, page - 1) * page_size)
                        .limit(page_size)
                    )
                )
        total = int(total or 0)
        total_pages = max(1, (total + page_size - 1) // page_size)
        safe_page = min(max(page, 1), total_pages)

        if safe_page != page:
            await self._show_cards(source, user_id, chat_id, safe_page)
            return

        if not rows:
            text = (
                "🎴 <b>Mis cartas</b>\n\n"
                "Todavía no tenés cartas. Las obtendrás con el gacha y otros eventos."
            )
            await source.edit_text(text, reply_markup=cards_keyboard([], safe_page, total_pages))
            return

        lines = [
            f"🎴 <b>Mis cartas</b> · página {safe_page}/{total_pages}",
            "",
        ]
        for row in rows:
            character_name = (
                row.character_id
                if row.character_id.startswith("fusion:")
                else get_character(row.character_id).name
            )
            lines.append(
                f"• <b>{character_name}</b> · {row.card_tier} · "
                f"{'✨ SHINY' if row.variant == 'shiny' else 'Normal'} · ×{row.copies}"
            )
            lines.append(f"  👗 {row.outfit}")
        lines.extend(("", "Elegí una carta para iniciar o completar una fusión UR."))
        await source.edit_text(
            "\n".join(lines),
            reply_markup=cards_keyboard(rows, safe_page, total_pages),
        )

    async def card_pick(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer(
                "Este panel solo funciona en tu chat privado con Sunna. 😰",
                show_alert=True,
            )
            return
        parts = (callback.data or "").split(":")
        if len(parts) != 4 or not parts[3].isdigit() or callback.message is None:
            await callback.answer("Carta inválida.", show_alert=True)
            return
        row_id = int(parts[3])
        chat_id = await self._community_chat_id(callback.from_user.id)
        if chat_id is None:
            await callback.answer("No hay una comunidad configurada.", show_alert=True)
            return

        async with self.database.session() as session:
            profile = await session.scalar(
                select(GameProfile).where(
                    GameProfile.user_id == callback.from_user.id,
                    GameProfile.chat_id == chat_id,
                )
            )
            row = None
            if profile is not None:
                row = await session.scalar(
                    select(GameCardCollection).where(
                        GameCardCollection.id == row_id,
                        GameCardCollection.profile_id == profile.id,
                        GameCardCollection.copies > 0,
                    )
                )
        if row is None:
            await callback.answer(
                "Esta carta ya no está disponible o no pertenece a tu colección.",
                show_alert=True,
            )
            return

        selected = self._card_selection.get(callback.from_user.id)
        if selected is None:
            self._card_selection[callback.from_user.id] = row_id
            await callback.message.edit_text(
                f"🎴 <b>Primera carta seleccionada</b>\n\n"
                f"Has elegido <b>{get_character(row.character_id).name if not row.character_id.startswith('fusion:') else row.character_id}</b> "
                f"· {row.card_tier} · {row.variant}.\n\n"
                "Elegí otra carta distinta para crear una UR.",
                reply_markup=cards_keyboard([row], 1, 1),
            )
            await callback.answer("Carta seleccionada.")
            return

        if selected == row_id:
            self._card_selection.pop(callback.from_user.id, None)
            await callback.answer("Selección cancelada.")
            await self._show_cards(callback.message, callback.from_user.id, chat_id, 1)
            return

        try:
            async with self.database.session(write=True) as session:
                profile = await session.scalar(
                    select(GameProfile).where(
                        GameProfile.user_id == callback.from_user.id,
                        GameProfile.chat_id == chat_id,
                    )
                )
                if profile is None:
                    raise ValueError("No tenés perfil de juego.")
                result = await self.card_service.fuse(
                    session,
                    profile_id=profile.id,
                    first_collection_id=selected,
                    second_collection_id=row_id,
                    seed=f"card-fusion:{callback.id}",
                )
        except ValueError as exc:
            self._card_selection.pop(callback.from_user.id, None)
            await callback.answer(str(exc), show_alert=True)
            await self._show_cards(callback.message, callback.from_user.id, chat_id, 1)
            return

        self._card_selection.pop(callback.from_user.id, None)
        await callback.message.edit_text(
            f"💠 <b>UR creada</b>\n\n"
            f"🎴 {result.card.name}\n"
            f"🏷️ UR · {'✨ SHINY' if result.card.variant.value == 'shiny' else 'Normal'}\n"
            f"👗 {result.card.outfit}\n"
            "La fusión consumió una copia de cada carta base.",
            reply_markup=cards_keyboard([], 1, 1),
        )
        await callback.answer("¡Fusión UR completada! 💠", show_alert=True)

    async def items(self, message: Message) -> None:
        if message.chat.type != 'private' or message.from_user is None:
            return
        chat_id = await self._community_chat_id(message.from_user.id)
        if chat_id is None:
            await message.answer('😰 Todavía no hay una comunidad configurada.')
            return
        async with self.database.session() as session:
            profile = await session.scalar(select(GameProfile).where(
                GameProfile.user_id == message.from_user.id,
                GameProfile.chat_id == chat_id,
            ))
            if profile is None:
                await message.answer('🎁 Todavía no tenés objetos.')
                return
            items = list(await session.scalars(select(GameItemInventory).where(
                GameItemInventory.profile_id == profile.id,
                GameItemInventory.quantity > 0,
            )))
        if not items:
            await message.answer('🎁 No tenés objetos para absorber todavía.')
            return
        lines = ['🎁 <b>Objetos de Sunna</b>', '']
        for item in items:
            gift = self.gift_service.gift_for_key(item.item_key)
            lines.append(f'• <b>{gift.name}</b> ×{item.quantity} — +{gift.experience} EXP')
        await message.answer('\n'.join(lines), reply_markup=item_inventory_keyboard(items, []))
        await self._observe_action('item_inventory', message.from_user.id, chat_id)

    async def gift_claim(self, callback: CallbackQuery) -> None:
        if callback.message is None or callback.from_user is None:
            await callback.answer('Regalo inválido.', show_alert=True)
            return
        chat = callback.message.chat
        if chat.type not in {'group', 'supergroup'}:
            await callback.answer('Este regalo se reclama en la comunidad.', show_alert=True)
            return
        if not self.settings.is_chat_allowed(chat.id, chat.type):
            await callback.answer('Esta comunidad no está autorizada.', show_alert=True)
            return
        parts = (callback.data or '').split(':')
        if len(parts) != 4 or not parts[3].isdigit():
            await callback.answer('Regalo inválido.', show_alert=True)
            return
        async with self.database.session(write=True) as session:
            profile = await MemberRepository().get_or_create_game_profile(
                session, callback.from_user.id, chat.id, commit=False
            )
            result = await self.gift_service.claim(
                session,
                drop_id=int(parts[3]),
                user_id=callback.from_user.id,
                chat_id=chat.id,
                profile_id=profile.id,
            )
            if result is None:
                await callback.answer('Este regalo ya fue reclamado, expiró o sus 3 plazas están ocupadas.', show_alert=True)
                return
        await self._observe_action('gift_claim', callback.from_user.id, chat.id)
        await callback.answer(
            f'🎁 Recibiste {result.gift.name} ×1. Inventario: {result.quantity}.\n'
            'Usalo desde /objetos para absorberlo con una waifu.',
            show_alert=True,
        )

    async def item_choose(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback) or callback.message is None:
            await callback.answer('Este panel solo funciona en tu chat privado con Sunna. 😰', show_alert=True)
            return
        parts = (callback.data or '').split(':')
        if len(parts) != 4:
            await callback.answer('Objeto inválido.', show_alert=True)
            return
        item_key = parts[3]
        chat_id = await self._community_chat_id(callback.from_user.id)
        if chat_id is None:
            await callback.answer('No hay una comunidad configurada.', show_alert=True)
            return
        async with self.database.session() as session:
            profile = await session.scalar(select(GameProfile).where(
                GameProfile.user_id == callback.from_user.id,
                GameProfile.chat_id == chat_id,
            ))
            if profile is None:
                await callback.answer('No tenés inventario.', show_alert=True)
                return
            item = await session.scalar(select(GameItemInventory).where(
                GameItemInventory.profile_id == profile.id,
                GameItemInventory.item_key == item_key,
                GameItemInventory.quantity > 0,
            ))
            characters = list(await session.scalars(select(GameCollection).where(
                GameCollection.profile_id == profile.id,
            )))
        if item is None or not characters:
            await callback.answer('Ese objeto o una waifu elegible no están disponibles.', show_alert=True)
            return
        await callback.message.edit_text(
            f'🎁 <b>{self.gift_service.gift_for_key(item_key).name}</b> — elegí qué waifu lo absorberá.',
            reply_markup=item_consume_keyboard(item_key, [get_character(row.character_id) for row in characters]),
        )
        await callback.answer()

    async def item_absorb(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback) or callback.message is None:
            await callback.answer('Este panel solo funciona en tu chat privado con Sunna. 😰', show_alert=True)
            return
        parts = (callback.data or '').split(':')
        if len(parts) != 5:
            await callback.answer('Absorción inválida.', show_alert=True)
            return
        item_key, character_id = parts[3], parts[4]
        chat_id = await self._community_chat_id(callback.from_user.id)
        if chat_id is None:
            await callback.answer('No hay una comunidad configurada.', show_alert=True)
            return
        async with self.database.session(write=True) as session:
            profile = await session.scalar(select(GameProfile).where(
                GameProfile.user_id == callback.from_user.id,
                GameProfile.chat_id == chat_id,
            ))
            if profile is None:
                await callback.answer('No tenés perfil de juego.', show_alert=True)
                return
            new_level = await self.gift_service.absorb(
                session,
                profile_id=profile.id,
                character_id=character_id,
                item_key=item_key,
            )
            if new_level is None:
                await callback.answer('El objeto ya no está disponible o la waifu no está en tu colección.', show_alert=True)
                return
        character = get_character(character_id)
        await callback.message.edit_text(
            f'✨ <b>{character.name}</b> absorbió el objeto.\n'
            f'📈 Nivel actual: <b>{new_level}/25</b>.',
        )
        await self._observe_action('item_absorb', callback.from_user.id, chat_id)
        await callback.answer('EXP aplicada. ✨', show_alert=True)
    async def detector(self, message: Message) -> None:
        if message.chat.type != 'private' or message.from_user is None:
            return
        chat_id = await self._community_chat_id(message.from_user.id)
        if chat_id is None:
            await message.answer('😰 Todavía no hay una comunidad configurada para el Detector.')
            return
        await self._start_detector(message, message.from_user.id, chat_id, message.text or '')

    async def detector_open(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer('El Waifu Detector funciona en tu chat privado con Sunna. 😰', show_alert=True)
            return
        chat_id = await self._community_chat_id(callback.from_user.id)
        if chat_id is None:
            await callback.answer('Todavía no hay una comunidad configurada.', show_alert=True)
            return
        await self._start_detector(callback.message, callback.from_user.id, chat_id, '')
        await callback.answer()

    async def _start_detector(
        self,
        source: Message,
        user_id: int,
        chat_id: int,
        command_text: str,
    ) -> None:
        async with self.database.session(write=True) as session:
            profiles = await session.scalars(
                select(GameProfile).where(
                    GameProfile.user_id == user_id,
                    GameProfile.chat_id == chat_id,
                )
            )
            profile = profiles.first()
            if profile is None:
                await source.answer('🎒 Primero necesitás una waifu en tu colección.')
                return
            rows = list(await session.scalars(
                select(GameCollection).where(GameCollection.profile_id == profile.id)
            ))
            if not rows:
                await source.answer('🎒 Primero necesitás una waifu en tu colección.')
                return
            parts = command_text.split(maxsplit=1)
            requested = parts[1].strip() if len(parts) == 2 else ''
            chosen = next((row for row in rows if row.character_id == requested), None)
            if chosen is None:
                chosen = max(rows, key=lambda row: (row.level, row.experience, row.character_id))
            started = await self.detector_service.start(
                session,
                user_id=user_id,
                chat_id=chat_id,
                day_key=self._mission_day_key(),
                character_id=chosen.character_id,
            )
            if started is None:
                await source.answer('📡 Ya usaste tus 3 oportunidades del Waifu Detector por hoy.')
                return
        character = get_character(chosen.character_id)
        await source.answer(
            f'📡 <b>WAIFU DETECTOR</b> — intento {started.use_number}/3\n\n'
            f'⚔️ Aparece <b>{started.mob.name}</b> (poder {started.mob.power}).\n'
            f'🎀 Waifu: <b>{character.name}</b> · Nv.{chosen.level}\n'
            'Derrotalo para ganar EXP para esa waifu.',
            reply_markup=detector_keyboard(started.round.id),
        )
        await self._observe_action('detector_start', user_id, chat_id)

    async def detector_fight(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer('Este panel solo funciona en tu chat privado con Sunna. 😰', show_alert=True)
            return
        parts = (callback.data or '').split(':')
        if len(parts) != 4 or not parts[3].isdigit() or callback.message is None:
            await callback.answer('Combate inválido.', show_alert=True)
            return
        chat_id = await self._community_chat_id(callback.from_user.id)
        if chat_id is None:
            await callback.answer('No hay una comunidad configurada.', show_alert=True)
            return
        async with self.database.session(write=True) as session:
            result, level_or_power, collection, mob = await self.detector_service.fight(
                session,
                round_id=int(parts[3]),
                user_id=callback.from_user.id,
                chat_id=chat_id,
            )
        if result == 'already_fought':
            await callback.answer('Este combate ya fue resuelto.', show_alert=True)
            return
        if result == 'expired':
            await callback.message.edit_text('📡 El combate del Detector expiró.')
            await callback.answer('Expiró.', show_alert=True)
            return
        if result == 'invalid' or mob is None or collection is None:
            await callback.answer('No pude validar este combate.', show_alert=True)
            return
        name = get_character(collection.character_id).name
        if result == 'won':
            await callback.message.edit_text(
                f'🏆 <b>Detector completado</b>\n\n'
                f'🐾 {mob.name} derrotado.\n'
                f'🎀 {name} quedó en <b>Nv.{collection.level}</b> · EXP {collection.experience}.\n'
                '✨ La EXP se aplicó una sola vez.',
            )
            await self._observe_action('detector_win', callback.from_user.id, chat_id)
            await callback.answer('¡Victoria! ⚔️', show_alert=True)
            return
        await callback.message.edit_text(
            f'💥 <b>Derrota</b>\n\n🐾 {mob.name} tenía más poder esta vez.\n'
            f'🎀 {name}: Nv.{collection.level}.',
        )
        await self._observe_action('detector_loss', callback.from_user.id, chat_id)
        await callback.answer('Perdiste este combate.', show_alert=True)
    async def missions_open(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer("Este panel solo funciona en tu chat privado con Sunna. 😰", show_alert=True)
            return
        chat_id = await self._community_chat_id(callback.from_user.id)
        if chat_id is None:
            await callback.answer("Todavía no hay una comunidad asociada a tu cuenta.", show_alert=True)
            return
        day_key = self._mission_day_key()
        async with self.database.session(write=True) as session:
            rows = await self.missions.list_progress(
                session,
                user_id=callback.from_user.id,
                chat_id=chat_id,
                day_key=day_key,
            )
        lines = ["🎯 <b>Misiones diarias</b>", f"📅 {day_key}", ""]
        for mission, progress in rows:
            status = "✅ Completada" if progress.claimed else f"{min(progress.progress, progress.target)}/{progress.target}"
            lines.append(f"• <b>{mission.label}</b> — {status} · +{mission.reward_points} pts")
        lines.extend(("", "Las recompensas se acreditan una sola vez al completar el objetivo."))
        if callback.message is not None:
            await callback.message.edit_text("\n".join(lines), reply_markup=game_hub_keyboard())
        await self._observe_action("missions_view", callback.from_user.id, chat_id)
        await callback.answer()

    async def missions_command(self, message: Message) -> None:
        if message.chat.type != "private" or message.from_user is None:
            return
        chat_id = await self._community_chat_id(message.from_user.id)
        if chat_id is None:
            await message.answer("😰 Todavía no hay una comunidad asociada a tu cuenta.")
            return
        day_key = self._mission_day_key()
        async with self.database.session(write=True) as session:
            rows = await self.missions.list_progress(
                session,
                user_id=message.from_user.id,
                chat_id=chat_id,
                day_key=day_key,
            )
        lines = ["🎯 <b>Misiones diarias</b>", f"📅 {day_key}", ""]
        for mission, progress in rows:
            status = "✅ Completada" if progress.claimed else f"{min(progress.progress, progress.target)}/{progress.target}"
            lines.append(
                f"• <b>{mission.label}</b> — {status} · +{mission.reward_points} pts"
            )
        lines.extend(
            (
                "",
                "El progreso se registra una sola vez por acción y las recompensas no pueden duplicarse.",
            )
        )
        await message.answer("\n".join(lines))
        await self._observe_action("missions_view", message.from_user.id, chat_id)

    async def _community_chat_id(self, user_id: int) -> int | None:
        async with self.database.session() as session:
            return await self.community.for_user(session, user_id)

    @staticmethod
    def _private_callback(callback: CallbackQuery) -> bool:
        """Reject forwarded/stale private-game buttons from other chat contexts."""
        message = callback.message
        return (
            message is not None
            and message.chat.type == "private"
            and message.chat.id == callback.from_user.id
        )

    async def game(self, message: Message) -> None:
        if message.chat.type != "private":
            return
        await message.answer("🎮 <b>Zona de juegos</b>", reply_markup=game_hub_keyboard())
        if message.from_user is not None:
            await self._observe_action("game_hub", message.from_user.id)

    async def gacha(self, message: Message) -> None:
        if message.chat.type != "private":
            return
        await message.answer(
            f"🎰 <b>Gacha de personajes</b>\nCada tirada cuesta {GACHA_COST_POINTS} puntos.",
            reply_markup=gacha_keyboard(),
        )
        if message.from_user is not None:
            await self._observe_action("gacha_open", message.from_user.id)

    async def gacha_open(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer("Este panel solo funciona en tu chat privado con Sunna. 😰", show_alert=True)
            return
        if callback.message is not None:
            await callback.message.edit_text(
                "🎰 <b>Gacha de personajes</b>",
                reply_markup=gacha_keyboard(),
            )
        await self._observe_action("gacha_open", callback.from_user.id)
        await callback.answer()

    async def waifus(self, message: Message) -> None:
        if message.chat.type != "private":
            return
        page = page_for(1)
        await message.answer(
            render_page(page),
            reply_markup=waifu_catalog_keyboard(
                page.page,
                page.total_pages,
                page.active_filter,
                page.characters,
            ),
        )
        if message.from_user is not None:
            await self._observe_action("waifu_catalog", message.from_user.id)

    async def waifu_catalog_filters(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer(
                "Este catálogo solo funciona en tu chat privado con Sunna. 😰",
                show_alert=True,
            )
            return
        if callback.message is not None:
            await callback.message.edit_text(
                "🔎 <b>Filtrar catálogo</b>\n\nElegí qué propiedad querés usar.",
                reply_markup=waifu_filter_categories_keyboard(),
            )
        await callback.answer()

    async def waifu_catalog_filter_options(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer(
                "Este catálogo solo funciona en tu chat privado con Sunna. 😰",
                show_alert=True,
            )
            return
        parts = (callback.data or "").split(":")
        if len(parts) != 4 or parts[3] not in {field.value for field in WaifuFilterField}:
            await callback.answer("Filtro inválido.", show_alert=True)
            return
        if callback.message is not None:
            await callback.message.edit_text(
                "🔎 <b>Elegí un valor</b>",
                reply_markup=waifu_filter_options_keyboard(parts[3]),
            )
        await callback.answer()

    async def waifu_catalog_filter_set(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer(
                "Este catálogo solo funciona en tu chat privado con Sunna. 😰",
                show_alert=True,
            )
            return
        parts = (callback.data or "").split(":")
        if len(parts) != 5:
            await callback.answer("Filtro inválido.", show_alert=True)
            return
        active_filter = WaifuFilter.from_code(parts[3], parts[4])
        if active_filter is None:
            await callback.answer("Filtro inválido.", show_alert=True)
            return
        page = page_for(1, active_filter=active_filter)
        if callback.message is not None:
            await callback.message.edit_text(
                render_page(page),
                reply_markup=waifu_catalog_keyboard(
                    page.page,
                    page.total_pages,
                    page.active_filter,
                    page.characters,
                ),
            )
        await self._observe_action(
            f"waifu_filter_{active_filter.field.value}_{active_filter.value}",
            callback.from_user.id,
        )
        await callback.answer("Filtro aplicado.")

    async def waifu_catalog_clear_filter(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer(
                "Este catálogo solo funciona en tu chat privado con Sunna. 😰",
                show_alert=True,
            )
            return
        page = page_for(1)
        if callback.message is not None:
            await callback.message.edit_text(
                render_page(page),
                reply_markup=waifu_catalog_keyboard(
                    page.page,
                    page.total_pages,
                ),
            )
        await self._observe_action("waifu_catalog_clear", callback.from_user.id)
        await callback.answer("Filtro quitado.")

    async def waifu_catalog_page(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer(
                "Este catálogo solo funciona en tu chat privado con Sunna. 😰",
                show_alert=True,
            )
            return
        parts = (callback.data or "").split(":")
        if len(parts) not in {4, 6} or not parts[3].isdigit():
            await callback.answer("Página inválida.", show_alert=True)
            return
        active_filter = None
        if len(parts) == 6:
            active_filter = WaifuFilter.from_code(parts[4], parts[5])
            if active_filter is None:
                await callback.answer("Filtro inválido.", show_alert=True)
                return
        page = page_for(int(parts[3]), active_filter=active_filter)
        if callback.message is not None:
            await callback.message.edit_text(
                render_page(page),
                reply_markup=waifu_catalog_keyboard(
                    page.page,
                    page.total_pages,
                    page.active_filter,
                    page.characters,
                ),
            )
        await self._observe_action("waifu_catalog_page", callback.from_user.id)
        await callback.answer()

    async def waifu_detail(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer(
                "Este catálogo solo funciona en tu chat privado con Sunna. 😰",
                show_alert=True,
            )
            return
        parts = (callback.data or "").split(":")
        if len(parts) not in {5, 7}:
            await callback.answer("Ficha inválida.", show_alert=True)
            return
        character_id = parts[3]
        try:
            page_number = int(parts[4])
        except ValueError:
            await callback.answer("Ficha inválida.", show_alert=True)
            return

        active_filter = None
        if len(parts) == 7:
            active_filter = WaifuFilter.from_code(parts[5], parts[6])
            if active_filter is None:
                await callback.answer("Filtro inválido.", show_alert=True)
                return

        try:
            character = get_character(character_id)
        except KeyError:
            await callback.answer("No encuentro esa waifu.", show_alert=True)
            return

        if callback.message is not None:
            detail_text = render_detail(character)
            art_file = next(
                (
                    candidate
                    for candidate in (
                        resolve_asset(path) for path in art_candidates_for(character_id)
                    )
                    if candidate is not None
                ),
                None,
            )
            if art_file is not None:
                await callback.message.edit_text("🎴 <b>Ficha de waifu</b>")
                await callback.message.answer_photo(
                    FSInputFile(str(art_file)),
                    caption=detail_text,
                    reply_markup=waifu_catalog_detail_keyboard(
                        page_number,
                        active_filter,
                    ),
                )
            else:
                await callback.message.edit_text(
                    detail_text,
                    reply_markup=waifu_catalog_detail_keyboard(
                        page_number,
                        active_filter,
                    ),
                )
        await self._observe_action("waifu_detail", callback.from_user.id)
        await callback.answer()

    async def inventory_callback(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer("Este botón solo funciona en tu chat privado con Sunna. 😰", show_alert=True)
            return
        chat_id = await self._community_chat_id(callback.from_user.id)
        if chat_id is None:
            await callback.answer("Todavía no hay una comunidad configurada.", show_alert=True)
            return
        await self._show_inventory(callback.message, callback.from_user.id, chat_id)
        await callback.answer()

    async def inventory(self, message: Message) -> None:
        if message.chat.type != "private" or message.from_user is None:
            return
        chat_id = await self._community_chat_id(message.from_user.id)
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
                    f"• {character.name} · {character.card_tier.value} · {character.element.value} · "
                    f"clase {item.rarity} · Nv.{item.level} · EXP {item.experience} · "
                    f"×{item.copies} · Evo.{item.evolution_stage}"
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
        if not self._private_callback(callback):
            await callback.answer("Este botón solo funciona en tu chat privado con Sunna. 😰", show_alert=True)
            return
        character_id = (callback.data or "").split(":", 2)[-1]
        if not character_id or callback.message is None:
            await callback.answer("Fusión inválida.", show_alert=True)
            return
        chat_id = await self._community_chat_id(callback.from_user.id)
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
        await self._observe_action("fusion", callback.from_user.id, chat_id)
        await callback.answer("¡Evolución completada! ✨")

    async def game_hub(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer("Este panel solo funciona en tu chat privado con Sunna. 😰", show_alert=True)
            return
        if callback.message is not None:
            await callback.message.edit_text("🎮 <b>Zona de juegos</b>", reply_markup=game_hub_keyboard())
        await self._observe_action("game_hub", callback.from_user.id)
        await callback.answer()

    async def combat(self, message: Message) -> None:
        if message.chat.type != "private":
            return
        await self._show_combat(message)

    async def combat_open(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer("Este panel solo funciona en tu chat privado con Sunna. 😰", show_alert=True)
            return
        if callback.message is not None:
            await self._show_combat(callback.message)
        await self._observe_action("combat_open", callback.from_user.id)
        await callback.answer()

    async def _show_combat(self, message: Message) -> None:
        taiga = get_character("taiga")
        await message.answer(
            f"⚔️ <b>{taiga.name}</b> — {taiga.anime}\n\n⚔️ {taiga.attack_name}\n"
            f"🛡️ {taiga.defense_name}\n✨ {taiga.special_name}\n\nElegí una acción.",
            reply_markup=combat_keyboard(),
        )

    async def gacha_roll(self, callback: CallbackQuery, bot: Bot | None = None) -> None:
        if not self._private_callback(callback):
            await callback.answer("Este panel solo funciona en tu chat privado con Sunna. 😰", show_alert=True)
            return
        chat_id = await self._community_chat_id(callback.from_user.id)
        if chat_id is None:
            await callback.answer("Todavía no hay una comunidad configurada.", show_alert=True)
            return

        async with self.database.session(write=True) as session:
            result = await self.gacha_service.roll(
                session,
                user_id=callback.from_user.id,
                chat_id=chat_id,
                seed=str(callback.id),
            )
            if result is None:
                await callback.answer(
                    f"Necesitás {GACHA_COST_POINTS} puntos para tirar.",
                    show_alert=True,
                )
                return
            mission_claimed, mission_balance, _, _ = await self._record_mission(
                session,
                user_id=callback.from_user.id,
                chat_id=chat_id,
                mission_key="gacha_roll",
                reference_type="gacha",
                reference_id=str(callback.id),
            )
            await session.commit()

        await self._observe_action("gacha_roll", callback.from_user.id, chat_id)

        if result.approval is not None:
            admin_id = self.settings.admin_user_id
            if not admin_id or bot is None:
                async with self.database.session(write=True) as session:
                    approval = await session.get(type(result.approval), result.approval.id)
                    if approval is not None and approval.status == "pending":
                        from app.game.rare_approval import decide

                        rejected = await decide(
                            session,
                            result.approval.id,
                            False,
                            commit=False,
                        )
                        if rejected is not None:
                            _, refunded_balance = await self.gacha_service.finalize_approval(
                                session,
                                rejected,
                            )
                            await session.commit()
                            await callback.answer(
                                "⚠️ El drop raro requiere un propietario configurado. "
                                f"Se devolvieron los {GACHA_COST_POINTS} puntos. Saldo: {refunded_balance}.",
                                show_alert=True,
                            )
                            return
            else:
                try:
                    await bot.send_message(
                        admin_id,
                        "🌟 <b>Solicitud de drop raro</b>\n\n"
                        f"Jugador: <code>{callback.from_user.id}</code>\n"
                        f"Comunidad: <code>{chat_id}</code>\n"
                        f"Personaje: <b>{result.character.name}</b>\n"
                        f"Carta: <b>{result.character.card_tier.value}</b> · elemento: <b>{result.character.element.value}</b>\n"
                        f"Clase: <b>{result.character.rarity.value}</b> · poder: <b>{result.character.power_score}/100</b>\n"
                        f"Popularidad: <b>{result.character.popularity_score}/100</b>"
                        f" · ranking: <b>#{result.character.popularity_rank}</b>\n"
                        f"Saldo restante: <b>{mission_balance if mission_claimed else result.remaining_points}</b>",
                        reply_markup=rare_approval_keyboard(result.approval.id),
                    )
                except Exception:
                    logger.exception("Could not notify owner about gacha approval=%s", result.approval.id)
            await callback.answer(
                f"🎰 {result.character.name} ({result.character.rarity.value}) salió. "
                "Quedó pendiente de aprobación del propietario.",
                show_alert=True,
            )
            return

        reaction = self._game_reaction(
            CharacterIntent.GAME_SUCCESS,
            callback.from_user.id + chat_id,
        )
        result_text = (
            f"🎉 ¡Salió {result.character.name} ({result.character.card_tier.value})! "
            f"Clase {result.character.rarity.value} · elemento {result.character.element.value} · "
            f"Saldo: {mission_balance if mission_claimed else result.remaining_points}"
        )
        if mission_claimed:
            result_text += "\n🎯 Misión diaria completada: +10 puntos."
        if result.pity_triggered:
            result_text += "\n✨ Protección de suerte activada."
        if reaction:
            result_text += f"\n\n🐍 Sunna: {reaction}"
        await callback.answer(result_text, show_alert=True)

    async def combat_action(self, callback: CallbackQuery) -> None:
        if not self._private_callback(callback):
            await callback.answer("Este panel solo funciona en tu chat privado con Sunna. 😰", show_alert=True)
            return
        action_key = callback.data.rsplit(":", 1)[-1]
        if action_key not in self.engine.ACTIONS:
            await callback.answer("Acción inválida.", show_alert=True)
            return
        taiga = get_character("taiga")
        result = self.engine.combat(taiga, taiga, action_key, callback.id)
        critical = " 💥 CRÍTICO" if result.critical else ""
        await self._observe_action("combat_action", callback.from_user.id)
        await callback.answer(f"{result.action.label}: {result.damage} daño{critical}", show_alert=True)

    async def encounter_answer(self, callback: CallbackQuery) -> None:
        parts = (callback.data or '').split(':')
        if len(parts) != 5 or parts[0] != 'game' or parts[1] != 'encounter' or parts[3] != 'answer':
            await callback.answer('Evento inválido.', show_alert=True)
            return
        encounter_id, index = parts[2], parts[4]
        if callback.message is None or not index.isdigit():
            await callback.answer('Respuesta inválida.', show_alert=True)
            return

        async with self.database.session(write=True) as session:
            encounter = await self.encounters.get(session, encounter_id)
            if encounter is None:
                await callback.answer('Este encuentro ya no existe.', show_alert=True)
                return
            if callback.message.chat.id != encounter.chat_id:
                await callback.answer('Este encuentro pertenece a otra comunidad. 😰', show_alert=True)
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
            option_index = int(index)
            if option_index >= len(options):
                await callback.answer('Respuesta inválida.', show_alert=True)
                return

            result = await self.encounters.claim_attempt(
                session, encounter_id, callback.from_user.id, options[option_index]
            )
            if result is EncounterAttemptResult.EXPIRED:
                await callback.answer('La waifu ya se fue. 😭', show_alert=True)
                return
            if result is EncounterAttemptResult.ALREADY_ATTEMPTED:
                await callback.answer('Ya usaste tu única oportunidad en este encuentro. 😭', show_alert=True)
                return
            if result is EncounterAttemptResult.FULL:
                await callback.answer('Este encuentro ya tiene sus 3 oportunidades ocupadas.', show_alert=True)
                return
            participant_count = await self.encounters.participant_count(session, encounter_id)
            if participant_count >= 3:
                await self.encounters.finish(session, encounter_id, "closed")

            if result is EncounterAttemptResult.WRONG:
                reaction = self._game_reaction(
                    CharacterIntent.GAME_MISS,
                    callback.from_user.id + callback.message.chat.id,
                )
                response_text = '❌ Fallaste. Esta oportunidad era solo tuya.'
                if participant_count >= 3:
                    response_text += '\n\n🚪 Ya se ocuparon las 3 oportunidades de este encuentro.'
                if reaction:
                    response_text += f'\n\n🐍 <b>Sunna:</b> {reaction}'
                await callback.answer(response_text, show_alert=True)
                return

            profile = await MemberRepository().get_or_create_game_profile(
                session, callback.from_user.id, encounter.chat_id, commit=False
            )
            owned, progress = await apply_capture_progression(
                session,
                profile_id=profile.id,
                character_id=character.id,
                rarity=encounter.rarity,
            )
            balance = await MemberRepository().add_points(
                session,
                user_id=callback.from_user.id,
                chat_id=encounter.chat_id,
                amount=progress.points_gained,
                reason='Captura de waifu',
                reference_type='encounter',
                reference_id=f"{encounter.id}:{callback.from_user.id}",
                commit=False,
            )
            mission_claimed, mission_balance, _, _ = await self._record_mission(
                session,
                user_id=callback.from_user.id,
                chat_id=encounter.chat_id,
                mission_key='capture_waifu',
                reference_type='encounter',
                reference_id=f"{encounter.id}:{callback.from_user.id}",
            )
            if mission_claimed:
                balance = mission_balance

        reaction = self._game_reaction(
            CharacterIntent.GAME_SUCCESS,
            callback.from_user.id + callback.message.chat.id,
        )
        result_text = (
            f'🎉 <b>{callback.from_user.first_name}</b> capturó a {character.name}!\n'
            f'✨ Clase {encounter.rarity} · colección ×{owned.copies}\n'
            f'⭐ +{progress.points_gained} puntos · saldo: {balance}\n'
            f'👥 Oportunidades ocupadas: <b>{participant_count}/3</b>'
        )
        if reaction:
            result_text += f'\n\n🐍 <b>Sunna:</b> {reaction}'
        await callback.message.edit_text(
            result_text,
            reply_markup=encounter_keyboard(encounter.id, options) if participant_count < 3 else None,
        )
        await self._observe_action(
            'encounter_capture', callback.from_user.id, encounter.chat_id
        )
        await callback.answer('¡CAPTURADA! 🎉', show_alert=True)
