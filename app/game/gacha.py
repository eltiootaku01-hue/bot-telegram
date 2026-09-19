from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RareDropApproval
from app.db.repositories import MemberRepository
from app.game.catalog import CHARACTERS
from app.game.engine import GameEngine
from app.game.models import Character, Rarity
from app.game.progression import apply_capture_progression
from app.game.rare_approval import propose


GACHA_COST_POINTS = 10
_RARITY_ORDER = {rarity: index for index, rarity in enumerate(Rarity)}


@dataclass(frozen=True, slots=True)
class GachaResult:
    rolled_rarity: Rarity
    character: Character
    remaining_points: int
    approval: RareDropApproval | None = None
    granted: bool = False


class GachaService:
    """Persistent gacha orchestration; rules stay local and deterministic."""

    def __init__(self, engine: GameEngine | None = None) -> None:
        self.engine = engine or GameEngine()

    @staticmethod
    def _candidate_for_roll(rolled: Rarity, seed: str) -> Character:
        candidates = [
            character
            for character in CHARACTERS.values()
            if _RARITY_ORDER[character.rarity] <= _RARITY_ORDER[rolled]
        ]
        if not candidates:
            raise RuntimeError("No characters are configured for the current gacha catalog")
        highest_available = max(_RARITY_ORDER[candidate.rarity] for candidate in candidates)
        top = [candidate for candidate in candidates if _RARITY_ORDER[candidate.rarity] == highest_available]
        index = abs(hash(seed)) % len(top)
        return sorted(top, key=lambda character: character.id)[index]

    async def roll(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        chat_id: int,
        seed: str,
    ) -> GachaResult | None:
        reference_id = seed
        balance = await MemberRepository().spend_points(
            session,
            user_id=user_id,
            chat_id=chat_id,
            amount=GACHA_COST_POINTS,
            reason="Tirada de gacha",
            reference_type="gacha",
            reference_id=reference_id,
            commit=False,
        )
        if balance is None:
            return None

        rolled = self.engine.roll_gacha(seed=seed)
        character = self._candidate_for_roll(rolled, seed)

        if _RARITY_ORDER[character.rarity] > _RARITY_ORDER[Rarity.C]:
            approval = await propose(
                session,
                character_id=character.id,
                rarity=character.rarity.value,
                target_user_id=user_id,
                target_chat_id=chat_id,
                commit=False,
            )
            await session.flush()
            return GachaResult(
                rolled_rarity=rolled,
                character=character,
                remaining_points=balance,
                approval=approval,
                granted=False,
            )

        profile = await MemberRepository().get_or_create_game_profile(
            session, user_id, chat_id, commit=False
        )
        await apply_capture_progression(
            session,
            profile_id=profile.id,
            character_id=character.id,
            rarity=character.rarity.value,
        )
        await session.flush()
        return GachaResult(
            rolled_rarity=rolled,
            character=character,
            remaining_points=balance,
            granted=True,
        )
