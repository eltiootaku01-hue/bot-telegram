from __future__ import annotations

import asyncio

from app.game.java_engine import default_java_engine
from app.game.models import Character, CombatAction, CombatResult, Rarity


class GameEngine:
    """Compatibility facade backed exclusively by the authoritative Java engine."""

    ACTIONS = {
        "attack": CombatAction("attack", "⚔️ Ataque", 10),
        "defend": CombatAction("defend", "🛡️ Defensa", 0),
        "special": CombatAction("special", "✨ Especial", 18),
    }

    def __init__(self) -> None:
        self._java = default_java_engine()

    def roll_gacha(self, seed: str | None = None) -> Rarity:
        return self._java.roll_gacha(seed=seed or "gacha:anonymous")

    async def roll_gacha_async(self, seed: str | None = None) -> Rarity:
        return await asyncio.to_thread(self.roll_gacha, seed)


    async def resolve_gacha_async(
        self,
        *,
        seed: str,
        d_streak: int,
        candidates: list[dict[str, str]],
        owned_character_ids: set[str] | frozenset[str],
        player_id: int,
        community_id: int,
    ) -> dict[str, object]:
        return await asyncio.to_thread(
            self.resolve_gacha,
            seed=seed,
            d_streak=d_streak,
            candidates=candidates,
            owned_character_ids=owned_character_ids,
            player_id=player_id,
            community_id=community_id,
        )

    def resolve_gacha(
        self,
        *,
        seed: str,
        d_streak: int,
        candidates: list[dict[str, str]],
        owned_character_ids: set[str] | frozenset[str],
        player_id: int,
        community_id: int,
    ) -> dict[str, object]:
        return self._java.resolve_gacha(
            seed=seed,
            d_streak=d_streak,
            candidates=candidates,
            owned_character_ids=owned_character_ids,
            player_id=player_id,
            community_id=community_id,
        )

    async def combat_async(
        self,
        attacker: Character,
        defender: Character,
        action_key: str,
        turn_id: str,
    ) -> CombatResult:
        return await asyncio.to_thread(
            self.combat,
            attacker,
            defender,
            action_key,
            turn_id,
        )

    def combat(
        self,
        attacker: Character,
        defender: Character,
        action_key: str,
        turn_id: str,
    ) -> CombatResult:
        if action_key not in self.ACTIONS:
            raise ValueError(f"Unknown combat action: {action_key}")
        return self._java.combat(
            attacker={
                "id": attacker.id,
                "name": attacker.name,
                "rarity": attacker.rarity.value,
                "level": attacker.level,
            },
            defender={
                "id": defender.id,
                "name": defender.name,
                "rarity": defender.rarity.value,
                "level": defender.level,
            },
            action=action_key,
            turn_id=turn_id,
        )

    def close(self) -> None:
        self._java.close()
