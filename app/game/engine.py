import hashlib
import random

from app.game.models import (
    Character,
    CombatAction,
    CombatResult,
    RARITY_MULTIPLIER,
    Rarity,
)


class GameEngine:
    """Pure deterministic-ish rules. Telegram and the database stay outside this layer."""

    ACTIONS = {
        "attack": CombatAction("attack", "⚔️ Ataque", 10),
        "defend": CombatAction("defend", "🛡️ Defensa", 0),
        "special": CombatAction("special", "✨ Especial", 18),
    }

    def roll_gacha(self, seed: str | None = None) -> Rarity:
        """Roll the game's rarity ladder. B+ is only a candidate until owner approval."""
        rng = random.Random(seed)
        roll = rng.random()
        if roll < 0.0005:
            return Rarity.SSS
        if roll < 0.002:
            return Rarity.SS
        if roll < 0.007:
            return Rarity.S
        if roll < 0.02:
            return Rarity.A
        if roll < 0.06:
            return Rarity.B
        if roll < 0.30:
            return Rarity.C
        return Rarity.D

    def combat(
        self,
        attacker: Character,
        defender: Character,
        action_key: str,
        turn_id: str,
    ) -> CombatResult:
        action = self.ACTIONS[action_key]
        if action_key == "defend":
            damage = 0
        else:
            digest = hashlib.sha256(f"{turn_id}:{attacker.id}:{defender.id}".encode()).digest()
            rng = random.Random(int.from_bytes(digest[:8], "big"))
            variance = rng.randint(-2, 3)
            critical = rng.random() < 0.08
            base = action.power + attacker.level * 2 + variance
            damage = max(1, int(base * RARITY_MULTIPLIER[attacker.rarity]))
            if critical:
                damage *= 2

        return CombatResult(
            attacker=attacker.name,
            defender=defender.name,
            damage=damage,
            action=action,
            critical=action_key != "defend" and damage > action.power * 2,
            defender_hp=max(0, 100 - damage),
        )
