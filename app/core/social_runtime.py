from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from sqlalchemy import select

from app.core.identity import BotIdentity
from app.core.module import BotModule
from app.core.presence import PresenceService
from app.core.social_activity import SocialActivityService
from app.core.social_director import SocialDirector
from app.core.social_turn import SocialTurnArbiter
from app.core.social_wake import SocialWakeController
from app.core.social_wake_store import SocialWakeStore
from app.core.time import utc_now
from app.db.database import Database
from app.db.models import Chat

logger = logging.getLogger(__name__)

SOCIAL_RUNTIME_TASK = "social.runtime"
DEFAULT_POLL_SECONDS = 30.0


class LocalSocialComposer:
    """Cheap local fallback for proactive speech.

    This intentionally does not call an LLM. The deterministic gate has already
    decided that a social opportunity exists; a future Brain provider can replace
    this composer without changing scheduling, persistence or turn arbitration.
    """

    _MESSAGES: dict[BotIdentity, tuple[str, ...]] = {
        BotIdentity.CARI: (
            "Bueno... está demasiado tranquilo por acá 👀",
            "¿Soy yo o el chat quedó en modo siesta? 😅",
        ),
        BotIdentity.SUNNA: (
            "…Está demasiado tranquilo. Hm.",
            "Qué silencio… no es que me moleste.",
        ),
        BotIdentity.CAMI: (
            "La actividad del chat cayó. Interesante.",
            "Todo bastante tranquilo por aquí. Lo registro.",
        ),
        BotIdentity.CHIE: (
            "¿Todo tranquilo por aquí? 🌸",
            "Parece que el chat está descansando un poquito.",
        ),
    }

    def compose(self, identity: BotIdentity, roll: int = 0) -> str:
        messages = self._MESSAGES[identity]
        return messages[max(0, roll) % len(messages)]


class SocialRuntime:
    """Autonomous wake → observe → decide → turn → speak loop for one identity."""

    def __init__(
        self,
        database: Database,
        identity: BotIdentity,
        *,
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
            if await self._tick_chat(bot, chat.id, now):
                return True
        return False

    async def _tick_chat(self, bot: Bot, chat_id: int, now) -> bool:
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
            snapshot = observed.to_snapshot(memory=_RuntimeMemory())
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

            # Only the highest-ranked candidate attempts the turn. This keeps
            # personality weights meaningful across the four independent bot
            # processes while still using one durable chat-level lock.
            if decision.candidates[0] is not self.identity:
                return False

            turn = await self.turns.acquire(session, chat_id, now=now)
            if turn is None:
                return False
            message = self.composer.compose(self.identity, roll=abs(chat_id) % 2)

        try:
            await bot.send_message(chat_id, message)
        except Exception:
            async with self.database.session() as session:
                await self.turns.abandon(session, turn, now=now)
            raise

        async with self.database.session() as session:
            await self.turns.complete(session, turn, now=now)
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


class _RuntimeMemory:
    """Zero-cost memory adapter; durable wake state supplies the runtime cooldown."""

    def minutes_since_last_bot_message(self, now) -> int:
        return 10_000

    def minutes_since_last_event(self, now) -> int:
        return 10_000


class SocialRuntimeModule(BotModule):
    """Start the autonomous social runtime with the normal module lifecycle."""

    name = "social_runtime"

    def __init__(self, database: Database, identity: BotIdentity) -> None:
        super().__init__()
        self.runtime = SocialRuntime(database, identity)

    def setup(self) -> None:
        return None

    async def on_startup(self, bot: Bot) -> None:
        self.tasks.start(SOCIAL_RUNTIME_TASK, self.runtime.run(bot))

    async def on_shutdown(self) -> None:
        self.runtime.stop()
        await super().on_shutdown()
