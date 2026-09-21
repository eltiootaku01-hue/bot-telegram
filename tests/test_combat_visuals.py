import pytest

from app.game.combat_visuals import (
    CombatSpriteVariant,
    SPRITE_SIZE,
    combat_sprite_path,
    validate_combat_result_for_animation,
)


def test_combat_sprite_paths_use_dual_pixel_art_contract() -> None:
    assert combat_sprite_path("asuna-yuuki") == (
        "assets/production/sprites/asuna-yuuki_idle.png"
    )
    assert combat_sprite_path("asuna-yuuki", CombatSpriteVariant.ATTACK) == (
        "assets/production/sprites/asuna-yuuki_attack.png"
    )
    assert combat_sprite_path("asuna-yuuki", "hit") == (
        "assets/production/sprites/asuna-yuuki_hit.png"
    )


@pytest.mark.parametrize("character_id", ["", "../asuna", r"asuna\attack"])
def test_combat_sprite_path_rejects_unsafe_ids(character_id: str) -> None:
    with pytest.raises(ValueError):
        combat_sprite_path(character_id)


def test_visual_contract_keeps_sprite_dimension_at_128() -> None:
    assert SPRITE_SIZE == 128


def test_engine_result_maps_to_visual_intent_without_recalculating_rules() -> None:
    assert validate_combat_result_for_animation(
        {"success": True, "payload": {"action": "attack", "damage": 99}}
    ) == "attack"
    assert validate_combat_result_for_animation(
        {"success": True, "payload": {"action": "defend", "defender_hp": 77}}
    ) == "idle"
    assert validate_combat_result_for_animation(
        {"success": True, "payload": {"action": "special", "damage": 140}}
    ) == "special_cut_in"
    assert validate_combat_result_for_animation({"success": False}) == "error"
