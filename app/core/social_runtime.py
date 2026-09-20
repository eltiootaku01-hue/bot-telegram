from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from sqlalchemy import select

from app.characters.director import CharacterDirector
from app.characters.models import CharacterIntent
from app.characters.routines import RoutineDirector
from app.core.config import Settings, get_settings
from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.core.presence import PresenceService
from app.core.social_activity import SocialActivityService
from app.core.social_director import SocialDirector
from app.core.social_memory import SocialMemory
from app.core.social_turn import SocialTurnArbiter
from app.core.social_wake import SocialWakeController
from app.core.social_wake_store import SocialWakeStore
from app.core.time import localize_utc, utc_now
from app.db.database import Database
from app.db.models import Chat

logger = logging.getLogger(__name__)

SOCIAL_RUNTIME_TASK = "social.runtime"
DEFAULT_POLL_SECONDS = 30.0


class LocalSocialComposer:
    """Deterministic authored composer for proactive social speech."""

    _LOCAL_INTENTS: dict[BotIdentity, CharacterIntent] = {
        BotIdentity.CARI: CharacterIntent.QUIET,
        BotIdentity.SUNNA: CharacterIntent.QUIET,
        BotIdentity.CAMI: CharacterIntent.BUSY,
        BotIdentity.CHIE: CharacterIntent.BUSY,
    }

    def __init__(
        self,
        director: CharacterDirector | None = None,
        routines: RoutineDirector | None = None,
    ) -> None:
        self.director = director or CharacterDirector()
        self.routines = routines or RoutineDirector(director=self.director)

    def compose(
        self,
        identity: BotIdentity,
        roll: int = 0,
        *,
        weekday: int | None = None,
        hour: int | None = None,
    ) -> str:
        if weekday is not None and hour is not None:
            scheduled = self.routines.choose(
                identity,
                weekday,
                hour,
                roll=roll,
            )
            if scheduled is not None:
                _, response = scheduled
                return response.scene.text

        intent = self._LOCAL_INTENTS[identity]
        response = self.director.choose(identity, intent, roll=roll)
        if response is not None:
            return response.scene.text
        return "..."


class SocialRuntime:
    """Autonomous wake → observe → decide → turn → speak loop for one identity."""

    def __init__(
        self,
        database: Database,
        identity: BotIdentity,
        *,
        settings: Settings | None = None,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        wake_controller: SocialWakeController | None = None,
        activity: SocialActivityService | None = None,
        director: SocialDirector | None = None,
        presence: PresenceService | None = None,
        wake_store: SocialWakeStore | None = None,
        turns: SocialTurnArbiter | None = None,
        composer: LocalSocialComposer | None = None,
    ) -> None:
        self.database = database
        self.identity = identity
        self.settings = settings or get_settings()
        self.poll_seconds = poll_seconds
        self.wakes = wake_controller or SocialWakeController()
        self.activity = activity or SocialActivityService()
        self.director = director or SocialDirector()
        self.presence = presence or PresenceService()
        self.wake_store = wake_store or SocialWakeStore()
        self.turns = turns or SocialTurnArbiter()
        self.composer = composer or LocalSocialComposer()
        self._stopping = asyncio.Event()

    async def run(self, bot: Bot) -> None:
        logger.info("Social runtime started: identity=%s", self.identity.value)
        try:
            while not self._stopping.is_set():
                worked = await self.tick(bot)
                if not worked:
                    try:
                        await asyncio.wait_for(self._stopping.wait(), timeout=self.poll_seconds)
                    except TimeoutError:
                        pass
        finally:
            logger.info("Social runtime stopped: identity=%s", self.identity.value)

    async def tick(self, bot: Bot) -> bool:
        now = utc_now()
        async with self.database.session() as session:
            chats = (
                await session.scalars(
                    select(Chat)
                    .where(Chat.type.in_(("group", "supergroup")))
                    .order_by(Chat.id)
                )
            ).all()

        for chat in chats:
            if not self.settings.is_chat_allowed(chat.id, chat.type):
                continue
            if await self._tick_chat(bot, chat.id, now):
                return True
        return False

    async def _tick_chat(self, bot: Bot, chat_id: int, now) -> bool:
        if not self.settings.is_chat_allowed(chat_id, "group") and not self.settings.is_chat_allowed(
            chat_id, "supergroup"
        ):
            return False

        async with self.database.session() as session:
            wake = await self.wake_store.get_or_create(
                session,
                chat_id,
                self.wakes.schedule(now, roll=abs(chat_id) % 31),
            )
            if not self.wakes.due(wake, now):
                return False

            presence = await self.presence.try_auto_resume(session, self.identity)
            if not presence.available:
                next_state = self.wakes.after_check(
                    wake, now, spoke=False, roll=abs(chat_id) % 31
                )
                await self.wake_store.save(session, chat_id, next_state)
                return True

            observed = await self.activity.observe(session, chat_id, now=now)
            snapshot = observed.to_snapshot(
                memory=SocialMemory(
                    last_bot_message_at=observed.last_bot_message_at,
                    last_event_at=observed.last_social_event_at,
                )
            )
            fatigue = await self._fatigue_map(session)
            decision = self.director.decide(
                snapshot,
                fatigue,
                cooldown_roll=abs(chat_id) % 31,
            )
            if not decision.should_speak or not decision.candidates:
                next_state = self.wakes.after_check(
                    wake,
                    now,
                    spoke=False,
                    roll=abs(chat_id) % 31,
                    chat_busy=decision.reason in {"human_conversation_active", "chat_busy"},
                )
                await self.wake_store.save(session, chat_id, next_state)
                return True

            if decision.candidates[0] is not self.identity:
                return False

            turn = await self.turns.acquire(
                session,
                chat_id=chat_id,
                window_key=now.strftime("%Y%m%d%H%M"),
                identity=self.identity,
            )
            if turn is None:
                return False

        world_now = localize_utc(now, self.settings.bot_world_timezone)
        message = self.composer.compose(
            self.identity,
            roll=abs(chat_id) % 2,
            weekday=world_now.weekday(),
            hour=world_now.hour,
        )

        # Proactive social speech is intentionally authored-only. The Brain may
        # assist explicit user-facing features, but enabling AI must not silently
        # replace the deterministic character runtime with free-form generation.
        try:
            if not (
                self.settings.is_chat_allowed(chat_id, "group")
                or self.settings.is_chat_allowed(chat_id, "supergroup")
            ):
                async with self.database.session() as session:
                    await self.turns.abandon(session, turn, reason="chat no longer authorized")
                return False
            await bot.send_message(chat_id, message)
        except Exception as exc:
            async with self.database.session() as session:
                await self.turns.abandon(session, turn, reason=str(exc))
            raise

        async with self.database.session(write=True) as session:
            chat = await session.get(Chat, chat_id)
            if chat is None:
                chat = Chat(id=chat_id, type="unknown")
                session.add(chat)
                await session.flush()
            chat.last_bot_message_at = now
            chat.last_social_event_at = now
            await self.turns.complete(session, turn)
            next_state = self.wakes.after_check(
                wake,
                now,
                spoke=True,
                roll=abs(chat_id) % 31,
            )
            await self.wake_store.save(session, chat_id, next_state)
            await self.presence.spend_energy(session, self.identity, amount=5)
        logger.info("Social message sent: identity=%s chat=%s", self.identity.value, chat_id)
        return True

    async def _fatigue_map(self, session) -> dict[BotIdentity, int]:
        result: dict[BotIdentity, int] = {}
        for identity in BotIdentity:
            state = await self.presence.get_or_create(session, identity)
            result[identity] = state.energy
        return result

    def stop(self) -> None:
        self._stopping.set()


class SocialRuntimeModule(BotModule):
    """Start the autonomous social runtime with the normal module lifecycle."""

    name = "social_runtime"

    def __init__(self, database: Database, identity: BotIdentity, settings: Settings | None = None) -> None:
        super().__init__()
        self.runtime = SocialRuntime(database, identity, settings=settings)

    def setup(self) -> None:
        return None

    async def on_startup(self, bot: Bot) -> None:
        self.tasks.start(SOCIAL_RUNTIME_TASK, self.runtime.run(bot))

    async def on_shutdown(self) -> None:
        self.runtime.stop()
        await super().on_shutdown()
