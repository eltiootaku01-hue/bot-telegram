from aiogram import F
from aiogram.types import Message

from app.characters.models import CharacterIntent
from app.characters.router import CharacterIntentRouter
from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.core.operator import is_tio_addressed
from app.db.database import Database
from app.services.world import WorldService


class ChatModule(BotModule):
    """Deterministic character conversation surface shared by all identities."""

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

    def setup(self) -> None:
        self.router.message.register(
            self.handle_text,
            F.text.func(self._should_handle_text),
        )

    def _should_handle_text(self, text: str) -> bool:
        if not text or is_tio_addressed(text):
            return False
        normalized = text.casefold().strip().strip("!?.,:;")
        intent = self.characters.classify(text)
        target = self.characters.target_identity(text)
        if self.identity is BotIdentity.CARI:
            if target is not None and target is not self.identity:
                return False
            return bool(normalized == "bot" or intent)
        return (
            self.characters.target_identity(text) is self.identity
            and (
                intent is not None
                or normalized == self.identity.value
                or len(self.characters.target_identities(text)) >= 2
            )
        )

    async def _observe_interaction(self, message: Message, speaker: BotIdentity, partner: BotIdentity) -> None:
        """Record a lightweight relationship-use signal after authored dialogue."""
        async with self.database.session() as session:
            relationship_key = f"{speaker.value}-{partner.value}"
            await self.world.observe(
                session,
                bot_identity=speaker,
                entry_type="relationship",
                entry_key=relationship_key,
            )
            await self.world.observe(
                session,
                bot_identity=speaker,
                entry_type="relationship",
                entry_key=relationship_key,
                scope_type="user",
                scope_id=str(message.from_user.id),
            )
            await self.world.observe(
                session,
                bot_identity=speaker,
                entry_type="relationship",
                entry_key=relationship_key,
                scope_type="user_chat",
                scope_id=f"{message.from_user.id}:{message.chat.id}",
            )

    async def _observe_scene(
        self,
        message: Message,
        scene_key: str,
        intent: CharacterIntent,
        speaker: BotIdentity,
        text: str,
        priority: int = 1,
    ) -> None:
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
        normalized = text.casefold().strip().strip("!?.,:;")
        targets = self.characters.target_identities(text)
        target = targets[0] if targets else None
        if normalized == "bot":
            intent = CharacterIntent.HELP
        elif intent is None and target is self.identity and normalized == self.identity.value:
            intent = CharacterIntent.CALLED
        elif intent is None and len(targets) >= 2 and target is self.identity:
            intent = CharacterIntent.UNKNOWN_TOPIC
        if intent is None:
            return

        response = None
        if (
            len(targets) >= 2
            and target is self.identity
            and targets[1] is not self.identity
        ):
            partner = targets[1]
            async with self.database.session() as session:
                continuity_count = await self.world.usage_count(
                    session,
                    bot_identity=self.identity,
                    entry_type="relationship",
                    entry_key=f"{self.identity.value}-{partner.value}",
                )
            response = self.characters.director.choose_interaction(
                self.identity,
                partner,
                intent,
                roll=(message.from_user.id + message.chat.id + continuity_count) % 17,
            )
        if response is None:
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
            await self._observe_interaction(
                message,
                response.scene.speaker,
                response.follow_up.speaker,
            )
            await self._observe_scene(
                message,
                response.follow_up.key,
                intent,
                response.follow_up.speaker,
                response.follow_up.text,
                response.follow_up.weight,
            )
