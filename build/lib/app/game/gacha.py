from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.db.models import GameCollection, GameGachaRoll, GameProfile, RareDropApproval
from app.db.repositories import MemberRepository
from app.game.card_service import CardCollectionService, card_for_gacha_character
from app.game.catalog import CHARACTERS, get_character
from app.game.cards import WaifuCard
from app.game.engine import GameEngine
from app.game.models import Character, Rarity
from app.game.progression import apply_capture_progression
from app.game.rare_approval import propose


GACHA_COST_POINTS = 10


@dataclass(frozen=True, slots=True)
class GachaResult:
    rolled_rarity: Rarity
    character: Character
    card: WaifuCard
    remaining_points: int
    approval: RareDropApproval | None = None
    granted: bool = False
    pity_triggered: bool = False


class GachaService:
    """Persistent gacha orchestration; Java owns rarity, pity and character selection."""

    def __init__(self, engine: GameEngine | None = None) -> None:
        self.engine = engine or GameEngine()
        self.cards = CardCollectionService()

    @staticmethod
    def _restore_result(
        roll: GameGachaRoll,
        approval: RareDropApproval | None,
        balance: int,
    ) -> GachaResult:
        character = get_character(roll.character_id)
        return GachaResult(
            rolled_rarity=Rarity(roll.rolled_rarity),
            character=character,
            card=card_for_gacha_character(character, seed=roll.roll_id),
            remaining_points=balance,
            approval=approval,
            granted=roll.granted,
            pity_triggered=roll.pity_triggered,
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
            if existing.user_id != user_id or existing.chat_id != chat_id:
                raise ValueError(
                    "Gacha roll reference belongs to another player or community"
                )
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

        roll = GameGachaRoll(
            roll_id=seed,
            user_id=user_id,
            chat_id=chat_id,
            rolled_rarity=Rarity.D.value,
            character_id="",
            granted=False,
        )
        try:
            async with session.begin_nested():
                session.add(roll)
                await session.flush()
        except IntegrityError:
            existing = await session.scalar(
                select(GameGachaRoll).where(GameGachaRoll.roll_id == seed)
            )
            if existing is None:
                raise
            if existing.user_id != user_id or existing.chat_id != chat_id:
                raise ValueError(
                    "Gacha roll reference belongs to another player or community"
                )
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

        profile = await MemberRepository().get_or_create_game_profile(
            session,
            user_id,
            chat_id,
            commit=False,
        )
        owned_rows = await session.scalars(
            select(GameCollection.character_id).where(
                GameCollection.profile_id == profile.id,
            )
        )
        owned_character_ids = frozenset(owned_rows)
        candidates = [
            {
                "id": character.id,
                "rarity": character.rarity.value,
            }
            for character in CHARACTERS.values()
        ]

        resolved = self.engine.resolve_gacha(
            seed=seed,
            d_streak=profile.gacha_d_streak,
            candidates=candidates,
            owned_character_ids=owned_character_ids,
            player_id=user_id,
            community_id=chat_id,
        )

        rolled = Rarity(str(resolved["rolled_rarity"]))
        pity_triggered = bool(resolved["pity_triggered"])
        next_d_streak = int(resolved["d_streak"])
        character_id = str(resolved["character_id"])
        if character_id not in CHARACTERS:
            raise RuntimeError(
                f"Java gacha returned unknown character id: {character_id}"
            )
        if character_id not in {item["id"] for item in candidates}:
            raise RuntimeError("Java gacha returned a character outside the submitted catalog")
        character = get_character(character_id)

        profile_update = await session.execute(
            update(GameProfile)
            .where(GameProfile.id == profile.id)
            .values(
                gacha_d_streak=next_d_streak,
                updated_at=utc_now(),
            )
        )
        if profile_update.rowcount != 1:
            raise RuntimeError("Player profile changed during gacha resolution")
        await session.refresh(profile)

        roll.rolled_rarity = rolled.value
        roll.pity_triggered = pity_triggered
        roll.character_id = character.id

        card = card_for_gacha_character(character, seed=seed)
        roll.card_id = card.card_id
        roll.card_variant = card.variant.value

        if character.rarity not in {Rarity.D, Rarity.C}:
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
                card=card,
                remaining_points=balance,
                approval=approval,
                granted=False,
                pity_triggered=pity_triggered,
            )

        await apply_capture_progression(
            session,
            profile_id=profile.id,
            character_id=character.id,
            rarity=character.rarity.value,
            potential_seed=f"gacha:{seed}",
        )
        await self.cards.grant(session, profile_id=profile.id, card=card)
        roll.granted = True
        await session.flush()
        return GachaResult(
            rolled_rarity=rolled,
            character=character,
            card=card,
            remaining_points=balance,
            granted=True,
            pity_triggered=pity_triggered,
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
            potential_seed=f"gacha:{roll.roll_id}",
        )
        card = card_for_gacha_character(
            get_character(approval.character_id),
            seed=roll.roll_id,
        )
        await self.cards.grant(session, profile_id=profile.id, card=card)
        await session.flush()
        await session.refresh(profile)
        return True, profile.points
