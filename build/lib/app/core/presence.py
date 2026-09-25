from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import BotIdentity
from app.core.time import utc_now
from app.db.models import BotPresence, BotPresenceState

MAX_ENERGY = 100
DEFAULT_REST_MINUTES = 30


@dataclass(frozen=True, slots=True)
class PresenceSnapshot:
    bot_identity: str
    status: BotPresence
    energy: int
    rest_until: datetime | None
    auto_resume: bool
    pc_idle_required: bool

    @property
    def available(self) -> bool:
        return self.status == BotPresence.ACTIVE


class PresenceService:
    """Shared fatigue/presence state for Cari, Sunna, Cami and Chie.

    Energy is deliberately independent from Telegram message count. Callers decide
    how expensive an action is, while this service owns persistence and transitions.
    """

    def __init__(self, *, max_energy: int = MAX_ENERGY) -> None:
        if max_energy <= 0:
            raise ValueError("max_energy must be positive")
        self.max_energy = max_energy

    async def get_or_create(
        self,
        session: AsyncSession,
        identity: BotIdentity | str,
        *,
        commit: bool = True,
    ) -> PresenceSnapshot:
        key = identity.value if isinstance(identity, BotIdentity) else str(identity)
        state = await session.scalar(
            select(BotPresenceState).where(BotPresenceState.bot_identity == key)
        )
        if state is None:
            state = BotPresenceState(bot_identity=key, updated_at=utc_now(), last_activity_at=utc_now())
            session.add(state)
            await session.flush()
        if commit:
            await session.commit()
        return self._snapshot(state)

    async def spend_energy(
        self,
        session: AsyncSession,
        identity: BotIdentity | str,
        amount: int,
        *,
        rest_minutes: int = DEFAULT_REST_MINUTES,
        auto_resume: bool | None = None,
        pc_idle_required: bool | None = None,
        commit: bool = True,
    ) -> PresenceSnapshot:
        if amount < 0:
            raise ValueError("energy amount cannot be negative")
        if rest_minutes <= 0:
            raise ValueError("rest_minutes must be positive")
        key = identity.value if isinstance(identity, BotIdentity) else str(identity)
        state = await session.scalar(
            select(BotPresenceState).where(BotPresenceState.bot_identity == key)
        )
        if state is None:
            state = BotPresenceState(bot_identity=key)
            session.add(state)
            await session.flush()

        now = utc_now()
        if state.status == BotPresence.RESTING and state.rest_until and state.rest_until > now:
            return self._snapshot(state)
        if state.status == BotPresence.MANUAL_OFF:
            return self._snapshot(state)

        state.energy = min(self.max_energy, state.energy + amount)
        state.last_activity_at = now
        state.updated_at = now
        if auto_resume is not None:
            state.auto_resume = auto_resume
        if pc_idle_required is not None:
            state.pc_idle_required = pc_idle_required

        if state.energy >= self.max_energy:
            state.energy = self.max_energy
            state.status = BotPresence.RESTING
            state.rest_until = now + timedelta(minutes=rest_minutes)

        if commit:
            await session.commit()
        return self._snapshot(state)

    async def wake(
        self,
        session: AsyncSession,
        identity: BotIdentity | str,
        *,
        force: bool = False,
        commit: bool = True,
    ) -> PresenceSnapshot:
        key = identity.value if isinstance(identity, BotIdentity) else str(identity)
        state = await session.scalar(
            select(BotPresenceState).where(BotPresenceState.bot_identity == key)
        )
        if state is None:
            state = BotPresenceState(bot_identity=key)
            session.add(state)
            await session.flush()
        if state.status == BotPresence.MANUAL_OFF and not force:
            return self._snapshot(state)
        state.status = BotPresence.ACTIVE
        state.rest_until = None
        state.energy = 0
        state.updated_at = utc_now()
        if commit:
            await session.commit()
        return self._snapshot(state)

    async def set_manual_off(
        self,
        session: AsyncSession,
        identity: BotIdentity | str,
        *,
        commit: bool = True,
    ) -> PresenceSnapshot:
        key = identity.value if isinstance(identity, BotIdentity) else str(identity)
        state = await session.scalar(
            select(BotPresenceState).where(BotPresenceState.bot_identity == key)
        )
        if state is None:
            state = BotPresenceState(bot_identity=key)
            session.add(state)
            await session.flush()
        state.status = BotPresence.MANUAL_OFF
        state.rest_until = None
        state.updated_at = utc_now()
        if commit:
            await session.commit()
        return self._snapshot(state)

    async def try_auto_resume(
        self,
        session: AsyncSession,
        identity: BotIdentity | str,
        *,
        pc_is_idle: bool = True,
        commit: bool = True,
    ) -> PresenceSnapshot:
        key = identity.value if isinstance(identity, BotIdentity) else str(identity)
        state = await session.scalar(
            select(BotPresenceState).where(BotPresenceState.bot_identity == key)
        )
        if state is None:
            return await self.get_or_create(session, key, commit=commit)
        now = utc_now()
        if state.status == BotPresence.RESTING and state.auto_resume:
            if state.rest_until and state.rest_until <= now and (not state.pc_idle_required or pc_is_idle):
                state.status = BotPresence.ACTIVE
                state.energy = 0
                state.rest_until = None
                state.updated_at = now
        if commit:
            await session.commit()
        return self._snapshot(state)

    @staticmethod
    def _snapshot(state: BotPresenceState) -> PresenceSnapshot:
        return PresenceSnapshot(
            bot_identity=state.bot_identity,
            status=BotPresence(state.status),
            energy=state.energy,
            rest_until=state.rest_until,
            auto_resume=state.auto_resume,
            pc_idle_required=state.pc_idle_required,
        )
