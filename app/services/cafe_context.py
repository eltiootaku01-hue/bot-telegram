from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import BotIdentity
from app.core.time import localize_utc, utc_now
from app.db.models import Chat, FanRequest, GameEncounter, RequestStatus, UserChat
from app.db.trivia_models import TriviaRound


@dataclass(frozen=True, slots=True)
class CafeContextSnapshot:
    """Live, low-cost state used to choose a contextual Café moment."""

    chat_id: int
    active_encounter: bool
    active_trivia: bool
    pending_requests: int
    recent_new_members: int
    recent_human_activity: bool
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class CafeContextMoment:
    """Authored non-canonical moment selected from live Café state."""

    key: str
    speaker: BotIdentity
    text: str
    reason: str


class CafeContextService:
    """Select authored Café moments from durable community/game state.

    No LLM is involved. The state is read-only and the chosen text comes from
    this module's authored repertoire.
    """

    NEW_MEMBER_WINDOW = timedelta(hours=24)
    HUMAN_ACTIVITY_WINDOW = timedelta(minutes=10)

    async def snapshot(
        self,
        session: AsyncSession,
        *,
        chat_id: int,
        now: datetime | None = None,
    ) -> CafeContextSnapshot:
        observed_at = now or utc_now()

        active_encounter = (
            await session.scalar(
                select(GameEncounter.id)
                .where(
                    GameEncounter.chat_id == chat_id,
                    GameEncounter.status == "active",
                    GameEncounter.expires_at > observed_at,
                )
                .limit(1)
            )
        ) is not None

        active_trivia = (
            await session.scalar(
                select(TriviaRound.id)
                .where(
                    TriviaRound.chat_id == chat_id,
                    TriviaRound.status == "active",
                    TriviaRound.expires_at > observed_at,
                )
                .limit(1)
            )
        ) is not None

        pending_requests = int(
            await session.scalar(
                select(func.count(FanRequest.id)).where(
                    FanRequest.chat_id == chat_id,
                    FanRequest.status.in_(
                        (
                            RequestStatus.PENDING_ADMIN.value,
                            RequestStatus.APPROVED.value,
                            RequestStatus.SCHEDULED.value,
                            RequestStatus.PROCESSING.value,
                        )
                    ),
                )
            )
            or 0
        )

        recent_new_members = int(
            await session.scalar(
                select(func.count(UserChat.id)).where(
                    UserChat.chat_id == chat_id,
                    UserChat.joined_at.is_not(None),
                    UserChat.joined_at >= observed_at - self.NEW_MEMBER_WINDOW,
                )
            )
            or 0
        )

        last_human_message_at = await session.scalar(
            select(Chat.last_human_message_at).where(Chat.id == chat_id)
        )
        recent_human_activity = (
            last_human_message_at is not None
            and observed_at - last_human_message_at <= self.HUMAN_ACTIVITY_WINDOW
        )

        return CafeContextSnapshot(
            chat_id=chat_id,
            active_encounter=active_encounter,
            active_trivia=active_trivia,
            pending_requests=pending_requests,
            recent_new_members=recent_new_members,
            recent_human_activity=recent_human_activity,
            observed_at=observed_at,
        )

    def choose(
        self,
        snapshot: CafeContextSnapshot,
        *,
        local_hour: int,
    ) -> CafeContextMoment:
        if not 0 <= local_hour <= 23:
            raise ValueError("local_hour must be between 0 and 23")

        if snapshot.active_encounter:
            return CafeContextMoment(
                key="context-active-waifumon",
                speaker=BotIdentity.SUNNA,
                text="Hay una waifu suelta. Si querés ayudar, no la dejes esperando.",
                reason="active_wild_encounter",
            )

        if snapshot.active_trivia:
            return CafeContextMoment(
                key="context-active-trivia",
                speaker=BotIdentity.SUNNA,
                text="La trivia sigue abierta. Estoy mirando las respuestas.",
                reason="active_trivia_round",
            )

        if snapshot.pending_requests > 0:
            return CafeContextMoment(
                key="context-pending-requests",
                speaker=BotIdentity.CAMI,
                text="Hay pedidos en la bandeja. Voy a revisar que cada uno tenga su información.",
                reason="pending_fan_requests",
            )

        if snapshot.recent_new_members > 0:
            return CafeContextMoment(
                key="context-new-members",
                speaker=BotIdentity.CHIE,
                text="Hoy pasó gente nueva por el Café. Revisaré que tenga todo lo necesario.",
                reason="recent_member_joins",
            )

        if snapshot.recent_human_activity:
            return CafeContextMoment(
                key="context-human-activity",
                speaker=BotIdentity.CARI,
                text="Hay movimiento en el Café. ☕ Me quedo por acá un rato.",
                reason="recent_human_activity",
            )

        if 6 <= local_hour < 12:
            return CafeContextMoment(
                key="context-morning",
                speaker=BotIdentity.CARI,
                text="La mañana está tranquila. Prepararé el Café para cuando llegue más gente.",
                reason="morning_quiet",
            )

        if 12 <= local_hour < 19:
            return CafeContextMoment(
                key="context-afternoon",
                speaker=BotIdentity.CAMI,
                text="Está bastante tranquilo. Buen momento para ordenar el archivo.",
                reason="afternoon_quiet",
            )

        return CafeContextMoment(
            key="context-evening",
            speaker=BotIdentity.CHIE,
            text="Ya es tarde. Revisaré los últimos avisos antes de cerrar recepción.",
            reason="evening_quiet",
        )

    async def moment(
        self,
        session: AsyncSession,
        *,
        chat_id: int,
        timezone_name: str,
        now: datetime | None = None,
    ) -> CafeContextMoment:
        observed_at = now or utc_now()
        snapshot = await self.snapshot(session, chat_id=chat_id, now=observed_at)
        local = localize_utc(observed_at, timezone_name)
        return self.choose(snapshot, local_hour=local.hour)
