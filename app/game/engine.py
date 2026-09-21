from __future__ import annotations

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
