from pathlib import Path

from app.game.java_engine import EngineClientConfig, WaifuMonJavaEngine
from app.game.models import Character, Rarity


def _engine() -> WaifuMonJavaEngine:
    root = Path(__file__).resolve().parents[1]
    return WaifuMonJavaEngine(
        config=EngineClientConfig(
            jar_path=root / "engine" / "waifumon" / "target" / "waifumon-engine.jar",
            java_command="java",
        )
    )


def test_java_engine_resolves_deterministic_gacha() -> None:
    engine = _engine()
    try:
        first = engine.roll_gacha(seed="python-java-contract")
        second = engine.roll_gacha(seed="python-java-contract")
    finally:
        engine.close()

    assert first is second
    assert first in set(Rarity)


def test_java_engine_resolves_combat_without_python_formula() -> None:
    engine = _engine()
    attacker = Character(
        id="taiga",
        name="Taiga",
        anime="Toradora!",
        rarity=Rarity.D,
        level=1,
    )
    defender = Character(
        id="asuna",
        name="Asuna",
        anime="Sword Art Online",
        rarity=Rarity.C,
        level=1,
    )
    try:
        first = engine.combat(
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
            action="attack",
            turn_id="turn-contract",
        )
        second = engine.combat(
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
            action="attack",
            turn_id="turn-contract",
        )
    finally:
        engine.close()

    assert first.damage == second.damage
    assert first.action.key == "attack"
    assert 0 <= first.defender_hp <= 100


def test_java_engine_resolves_progression_contract() -> None:
    engine = _engine()
    try:
        result = engine.progression(
            level=5,
            experience=495,
            evolution_stage=1,
            gained=10,
            copies=3,
        )
    finally:
        engine.close()

    assert result["level"] == 6
    assert result["experience"] == 5
    assert result["evolution_stage"] == 2
    assert result["evolved"] is True
    assert result["copies"] == 3
