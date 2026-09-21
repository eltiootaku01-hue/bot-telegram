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


def fake_png(
    width: int = SPRITE_SIZE,
    height: int = SPRITE_SIZE,
    *,
    alpha: bool = True,
) -> bytes:
    import struct
    import zlib

    color_type = 6 if alpha else 2
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    def chunk(name: bytes, payload: bytes) -> bytes:
        return (
            len(payload).to_bytes(4, "big")
            + name
            + payload
            + zlib.crc32(name + payload).to_bytes(4, "big")
        )

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IEND", b"")


def test_validate_combat_sprite_asset_accepts_128_rgba_png(tmp_path) -> None:
    from app.game.combat_visuals import validate_combat_sprite_asset

    path = tmp_path / "idle.png"
    path.write_bytes(fake_png())

    result = validate_combat_sprite_asset(path)

    assert result.valid is True
    assert result.width == SPRITE_SIZE
    assert result.height == SPRITE_SIZE
    assert result.transparent is True


def test_validate_combat_sprite_asset_rejects_opaque_png(tmp_path) -> None:
    from app.game.combat_visuals import validate_combat_sprite_asset

    path = tmp_path / "idle.png"
    path.write_bytes(fake_png(alpha=False))

    result = validate_combat_sprite_asset(path)

    assert result.valid is False
    assert "alpha" in result.reason


def test_validate_combat_sprite_asset_rejects_wrong_dimensions(tmp_path) -> None:
    from app.game.combat_visuals import validate_combat_sprite_asset

    path = tmp_path / "idle.png"
    path.write_bytes(fake_png(64, 64))

    result = validate_combat_sprite_asset(path)

    assert result.valid is False
    assert "128x128" in result.reason
