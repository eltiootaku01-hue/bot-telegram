from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GameGachaRoll, RareDropApproval
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
        top = sorted(
            [
                candidate
                for candidate in candidates
                if _RARITY_ORDER[candidate.rarity] == highest_available
            ],
            key=lambda character: character.id,
        )
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % len(top)
        return top[index]

    @staticmethod
    def _restore_result(roll: GameGachaRoll, approval: RareDropApproval | None, balance: int) -> GachaResult:
        return GachaResult(
            rolled_rarity=Rarity(roll.rolled_rarity),
            character=CHARACTERS[roll.character_id],
            remaining_points=balance,
            approval=approval,
            granted=roll.granted,
        )

    async def roll(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        chat_id: int,
        seed: str,
    ) -> GachaResult | None:
        existing = await session.scalar(
            select(GameGachaRoll).where(GameGachaRoll.roll_id == seed)
        )
        if existing is not None:
            approval = (
                await session.get(RareDropApproval, existing.approval_id)
                if existing.approval_id is not None
                else None
            )
            profile = await MemberRepository().get_or_create_game_profile(
                session, user_id, chat_id, commit=False
            )
            await session.refresh(profile)
            return self._restore_result(existing, approval, profile.points)

        try:
            async with session.begin_nested():
                roll = GameGachaRoll(
                    roll_id=seed,
                    user_id=user_id,
                    chat_id=chat_id,
                    rolled_rarity=self.engine.roll_gacha(seed=seed).value,
                    character_id="",
                    granted=False,
                )
                session.add(roll)
                await session.flush()
        except IntegrityError:
            existing = await session.scalar(
                select(GameGachaRoll).where(GameGachaRoll.roll_id == seed)
            )
            if existing is None:
                raise
            approval = (
                await session.get(RareDropApproval, existing.approval_id)
                if existing.approval_id is not None
                else None
            )
            profile = await MemberRepository().get_or_create_game_profile(
                session, user_id, chat_id, commit=False
            )
            await session.refresh(profile)
            return self._restore_result(existing, approval, profile.points)

        rolled = Rarity(roll.rolled_rarity)
        character = self._candidate_for_roll(rolled, seed)
        roll.character_id = character.id

        balance = await MemberRepository().spend_points(
            session,
            user_id=user_id,
            chat_id=chat_id,
            amount=GACHA_COST_POINTS,
            reason="Tirada de gacha",
            reference_type="gacha",
            reference_id=seed,
            commit=False,
        )
        if balance is None:
            await session.delete(roll)
            await session.flush()
            return None

        if _RARITY_ORDER[character.rarity] > _RARITY_ORDER[Rarity.C]:
            approval = await propose(
                session,
                character_id=character.id,
                rarity=character.rarity.value,
                target_user_id=user_id,
                target_chat_id=chat_id,
                commit=False,
            )
            roll.approval_id = approval.id
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
        roll.granted = True
        await session.flush()
        return GachaResult(
            rolled_rarity=rolled,
            character=character,
            remaining_points=balance,
            granted=True,
        )

    @staticmethod
    async def _claim_reward(session: AsyncSession, roll_id: int) -> bool:
        """Atomically move a persisted gacha roll from ungranted to granted."""
        result = await session.execute(
            update(GameGachaRoll)
            .where(
                GameGachaRoll.id == roll_id,
                GameGachaRoll.granted.is_(False),
            )
            .values(granted=True)
        )
        return result.rowcount == 1

    async def finalize_approval(
        self,
        session: AsyncSession,
        approval: RareDropApproval,
    ) -> tuple[bool, int]:
        """Grant an approved rare drop, or leave it untouched when already finalized."""
        roll = await session.scalar(
            select(GameGachaRoll).where(GameGachaRoll.approval_id == approval.id)
        )
        if approval.status != "approved":
            if approval.status == "rejected":
                balance = await MemberRepository().add_points(
                    session,
                    user_id=approval.target_user_id,
                    chat_id=approval.target_chat_id,
                    amount=GACHA_COST_POINTS,
                    reason="Reembolso de gacha rechazado",
                    reference_type="gacha_refund",
                    reference_id=str(approval.id),
                    commit=False,
                )
                return False, balance
            return False, (
                await MemberRepository().get_or_create_game_profile(
                    session,
                    approval.target_user_id,
                    approval.target_chat_id,
                    commit=False,
                )
            ).points

        if roll is None:
            raise RuntimeError("Approved gacha drop has no persistent roll")

        if not await self._claim_reward(session, roll.id):
            profile = await MemberRepository().get_or_create_game_profile(
                session,
                approval.target_user_id,
                approval.target_chat_id,
                commit=False,
            )
            await session.refresh(profile)
            return True, profile.points

        profile = await MemberRepository().get_or_create_game_profile(
            session,
            approval.target_user_id,
            approval.target_chat_id,
            commit=False,
        )
        await apply_capture_progression(
            session,
            profile_id=profile.id,
            character_id=approval.character_id,
            rarity=approval.rarity,
        )
        await session.flush()
        await session.refresh(profile)
        return True, profile.points
