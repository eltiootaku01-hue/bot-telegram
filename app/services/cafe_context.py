from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import BotIdentity
from app.core.time import localize_utc, utc_now
from app.db.models import Chat, FanRequest, GameEncounter, RequestStatus, User, UserChat
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


@dataclass(frozen=True, slots=True)
class _AuthoredVariant:
    speaker: BotIdentity
    key: str
    text: str
    reason: str


class CafeContextService:
    """Select authored Café moments from durable community/game state.

    No LLM is involved. The state is read-only and the chosen text comes from
    this module's authored repertoire.
    """

    NEW_MEMBER_WINDOW = timedelta(hours=24)
    HUMAN_ACTIVITY_WINDOW = timedelta(minutes=10)

    _VARIANTS: dict[str, tuple[_AuthoredVariant, ...]] = {
        "active_wild_encounter": (
            _AuthoredVariant(
                BotIdentity.SUNNA,
                "context-active-waifumon",
                "Hay una waifu suelta. Si querés ayudar, no la dejes esperando.",
                "active_wild_encounter",
            ),
            _AuthoredVariant(
                BotIdentity.SUNNA,
                "context-active-waifumon-2",
                "La vi. El encuentro sigue abierto. Todavía hay tiempo.",
                "active_wild_encounter",
            ),
            _AuthoredVariant(
                BotIdentity.CARI,
                "context-active-waifumon-3",
                "¡Hay una waifu suelta en el Café! Vamos, que no se nos escape. ✨",
                "active_wild_encounter",
            ),
        ),
        "active_trivia_round": (
            _AuthoredVariant(
                BotIdentity.SUNNA,
                "context-active-trivia-1",
                "La trivia sigue abierta. Estoy mirando las respuestas.",
                "active_trivia_round",
            ),
            _AuthoredVariant(
                BotIdentity.SUNNA,
                "context-active-trivia-2",
                "Todavía no termina. Fijate bien antes de responder.",
                "active_trivia_round",
            ),
            _AuthoredVariant(
                BotIdentity.CARI,
                "context-active-trivia-3",
                "¡La trivia sigue viva! A ver quién se queda con la victoria. ☕",
                "active_trivia_round",
            ),
        ),
        "pending_fan_requests": (
            _AuthoredVariant(
                BotIdentity.CAMI,
                "context-pending-requests-1",
                "Hay pedidos en la bandeja. Voy a revisar que cada uno tenga su información.",
                "pending_fan_requests",
            ),
            _AuthoredVariant(
                BotIdentity.CAMI,
                "context-pending-requests-2",
                "Tengo pedidos pendientes. Primero compruebo los datos y después seguimos.",
                "pending_fan_requests",
            ),
            _AuthoredVariant(
                BotIdentity.CHIE,
                "context-pending-requests-3",
                "Hay pedidos esperando revisión. Voy a ordenar la lista para que nada se pierda.",
                "pending_fan_requests",
            ),
        ),
        "recent_member_joins": (
            _AuthoredVariant(
                BotIdentity.CHIE,
                "context-new-members-1",
                "Hoy pasó gente nueva por el Café. Revisaré que tenga todo lo necesario.",
                "recent_member_joins",
            ),
            _AuthoredVariant(
                BotIdentity.CHIE,
                "context-new-members-2",
                "Hay integrantes nuevos. Voy a asegurarme de que encuentren las reglas y los temas correctos.",
                "recent_member_joins",
            ),
            _AuthoredVariant(
                BotIdentity.CARI,
                "context-new-members-3",
                "¡Llegó gente nueva! Hay que hacerles un lugarcito. ☕",
                "recent_member_joins",
            ),
        ),
        "recent_human_activity": (
            _AuthoredVariant(
                BotIdentity.CARI,
                "context-human-activity-1",
                "Hay movimiento en el Café. ☕ Me quedo por acá un rato.",
                "recent_human_activity",
            ),
            _AuthoredVariant(
                BotIdentity.CARI,
                "context-human-activity-2",
                "Escucho bastante charla hoy. Mejor me quedo cerca del mostrador.",
                "recent_human_activity",
            ),
            _AuthoredVariant(
                BotIdentity.CAMI,
                "context-human-activity-3",
                "Hay bastante actividad. Esperaré un momento para ver qué necesita cada uno.",
                "recent_human_activity",
            ),
        ),
        "morning_quiet": (
            _AuthoredVariant(
                BotIdentity.CARI,
                "context-morning-1",
                "La mañana está tranquila. Prepararé el Café para cuando llegue más gente.",
                "morning_quiet",
            ),
            _AuthoredVariant(
                BotIdentity.CARI,
                "context-morning-2",
                "Todavía está tranquilo. Voy dejando todo listo para el día.",
                "morning_quiet",
            ),
            _AuthoredVariant(
                BotIdentity.CHIE,
                "context-morning-3",
                "Recién empieza el día. Voy a revisar que la recepción esté en orden.",
                "morning_quiet",
            ),
        ),
        "afternoon_quiet": (
            _AuthoredVariant(
                BotIdentity.CAMI,
                "context-afternoon-1",
                "Está bastante tranquilo. Buen momento para ordenar el archivo.",
                "afternoon_quiet",
            ),
            _AuthoredVariant(
                BotIdentity.CAMI,
                "context-afternoon-2",
                "La tarde viene tranquila. Puedo aprovechar para revisar algunas fichas.",
                "afternoon_quiet",
            ),
            _AuthoredVariant(
                BotIdentity.CARI,
                "context-afternoon-3",
                "Una tarde tranquila... casi sospechosa. Bueno, disfruto el juguito. ☕",
                "afternoon_quiet",
            ),
        ),
        "evening_quiet": (
            _AuthoredVariant(
                BotIdentity.CHIE,
                "context-evening-1",
                "Ya es tarde. Revisaré los últimos avisos antes de cerrar recepción.",
                "evening_quiet",
            ),
            _AuthoredVariant(
                BotIdentity.CHIE,
                "context-evening-2",
                "La ciudad se está calmando. Haré una última revisión y listo.",
                "evening_quiet",
            ),
            _AuthoredVariant(
                BotIdentity.SUNNA,
                "context-evening-3",
                "Está tranquilo. Me quedo un rato antes de irme.",
                "evening_quiet",
            ),
        ),
    }

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
                select(func.count(UserChat.id))
                .join(User, User.id == UserChat.user_id)
                .where(
                    UserChat.chat_id == chat_id,
                    User.is_bot.is_(False),
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
        variant_seed: int = 0,
    ) -> CafeContextMoment:
        if not 0 <= local_hour <= 23:
            raise ValueError("local_hour must be between 0 and 23")

        if snapshot.active_encounter:
            return self._pick("active_wild_encounter", variant_seed)

        if snapshot.active_trivia:
            return self._pick("active_trivia_round", variant_seed)

        if snapshot.pending_requests > 0:
            return self._pick("pending_fan_requests", variant_seed)

        if snapshot.recent_new_members > 0:
            return self._pick("recent_member_joins", variant_seed)

        if snapshot.recent_human_activity:
            return self._pick("recent_human_activity", variant_seed)

        if 6 <= local_hour < 12:
            return self._pick("morning_quiet", variant_seed)

        if 12 <= local_hour < 19:
            return self._pick("afternoon_quiet", variant_seed)

        return self._pick("evening_quiet", variant_seed)

    @classmethod
    def _pick(cls, reason: str, variant_seed: int) -> CafeContextMoment:
        variants = cls._VARIANTS[reason]
        variant = variants[abs(variant_seed) % len(variants)]
        return CafeContextMoment(
            key=variant.key,
            speaker=variant.speaker,
            text=variant.text,
            reason=variant.reason,
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
        # Stable within the same world day/community, so repeated /momento calls
        # are varied across days without depending on process-local randomness.
        day_key = local.date().isoformat()
        seed = int.from_bytes(
            f"{chat_id}:{day_key}".encode("utf-8"),
            "little",
        )
        return self.choose(snapshot, local_hour=local.hour, variant_seed=seed)
