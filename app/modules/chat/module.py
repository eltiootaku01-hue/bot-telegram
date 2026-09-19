from aiogram import F
from aiogram.types import Message

from app.characters.models import CharacterIntent
from app.characters.router import CharacterIntentRouter
from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.db.database import Database
from app.services.world import WorldService
from app.services.world_catalog import WORLD_CATALOG


class ChatModule(BotModule):
    """Deterministic community conversation surface for Cari."""

    name = "chat"

    def __init__(
        self,
        database: Database,
        identity: BotIdentity = BotIdentity.CARI,
        world: WorldService | None = None,
    ) -> None:
        super().__init__()
        self.database = database
        self.identity = identity
        self.characters = CharacterIntentRouter()
        self.world = world or WorldService()
        self._catalog_seeded = False

    def setup(self) -> None:
        self.router.message.register(
            self.handle_text,
            F.text.func(self._should_handle_text),
        )

    def _should_handle_text(self, text: str) -> bool:
        return bool(text and (text.casefold().strip() == "bot" or self.characters.classify(text)))

    async def _seed_catalog(self) -> None:
        if self._catalog_seeded:
            return
        async with self.database.session() as session:
            from app.characters.repertoire import REPERTOIRE

            for item in WORLD_CATALOG:
                await self.world.register_catalog_entry(
                    session,
                    bot_identity=item.bot_identity,
                    entry_type=item.entry_type,
                    entry_key=item.entry_key,
                    label=item.label,
                    priority=item.priority,
                )
            for scene in REPERTOIRE:
                await self.world.register_catalog_entry(
                    session,
                    bot_identity=scene.speaker,
                    entry_type="scene",
                    entry_key=scene.key,
                    label=scene.text,
                    priority=scene.weight,
                )
        self._catalog_seeded = True

    async def on_startup(self, bot) -> None:
        await self._seed_catalog()

    async def _observe_scene(
        self,
        message: Message,
        scene_key: str,
        intent: CharacterIntent,
        speaker: BotIdentity,
        text: str,
        priority: int = 1,
    ) -> None:
        await self._seed_catalog()
        async with self.database.session() as session:
            await self.world.register_catalog_entry(
                session,
                bot_identity=speaker,
                entry_type="scene",
                entry_key=scene_key,
                label=text,
                priority=priority,
            )
            await self.world.observe(
                session,
                bot_identity=speaker,
                entry_type="scene",
                entry_key=scene_key,
            )
            await self.world.observe(
                session,
                bot_identity=self.identity,
                entry_type="intent",
                entry_key=intent.value,
                scope_type="user",
                scope_id=str(message.from_user.id),
            )
            await self.world.observe(
                session,
                bot_identity=speaker,
                entry_type="scene",
                entry_key=scene_key,
                scope_type="user_chat",
                scope_id=f"{message.from_user.id}:{message.chat.id}",
            )

    async def handle_text(self, message: Message) -> None:
        if message.from_user is None or not message.text:
            return
        text = message.text.strip()
        intent = self.characters.classify(text)
        if text.casefold() == "bot":
            intent = CharacterIntent.HELP
        if intent is None:
            return
        response = self.characters.director.choose(
            self.identity,
            intent,
            roll=(message.from_user.id + message.chat.id) % 17,
        )
        if response is None:
            return
        await message.answer(response.scene.text)
        await self._observe_scene(
            message,
            response.scene.key,
            intent,
            response.scene.speaker,
            response.scene.text,
            response.scene.weight,
        )
        if response.follow_up is not None:
            await message.answer(response.follow_up.text)
            await self._observe_scene(
                message,
                response.follow_up.key,
                intent,
                response.follow_up.speaker,
                response.follow_up.text,
                response.follow_up.weight,
            )
