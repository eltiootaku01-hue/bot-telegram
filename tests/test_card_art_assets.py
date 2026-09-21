from pathlib import Path

import pytest

from app.game.card_art_assets import (
    CARD_ART_HEIGHT,
    CARD_ART_MAX_BYTES,
    CARD_ART_MIN_BYTES,
    CARD_ART_WIDTH,
    card_asset_path,
    jpeg_dimensions,
    validate_card_asset,
)


def fake_jpeg(width: int = CARD_ART_WIDTH, height: int = CARD_ART_HEIGHT, padding: int = 60_000) -> bytes:
    sof_payload = (
        b"\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03"
        + b"\x01\x11\x00"
        + b"\x02\x11\x00"
        + b"\x03\x11\x00"
    )
    sof = b"\xff\xc0" + (len(sof_payload) + 2).to_bytes(2, "big") + sof_payload
    return b"\xff\xd8" + sof + (b"\x00" * padding) + b"\xff\xd9"


def test_card_asset_path_is_deterministic() -> None:
    assert card_asset_path("yor-forger", "normal") == "assets/production/cards/yor-forger--normal.jpg"
    assert card_asset_path("yor-forger", "shiny") == "assets/production/cards/yor-forger--shiny.jpg"


@pytest.mark.parametrize("variant", ["invalid", ""])
def test_card_asset_path_rejects_invalid_variant(variant: str) -> None:
    with pytest.raises(ValueError):
        card_asset_path("yor-forger", variant)


def test_jpeg_dimensions_reads_portrait_target(tmp_path: Path) -> None:
    path = tmp_path / "sample.jpg"
    path.write_bytes(fake_jpeg())
    assert jpeg_dimensions(path) == (CARD_ART_WIDTH, CARD_ART_HEIGHT)


def test_validate_card_asset_accepts_target_contract(tmp_path: Path) -> None:
    path = tmp_path / "sample.jpg"
    path.write_bytes(fake_jpeg())

    result = validate_card_asset(path)

    assert result.valid is True
    assert result.width == CARD_ART_WIDTH
    assert result.height == CARD_ART_HEIGHT
    assert result.size_bytes >= CARD_ART_MIN_BYTES
    assert result.size_bytes <= CARD_ART_MAX_BYTES


def test_validate_card_asset_rejects_wrong_dimensions(tmp_path: Path) -> None:
    path = tmp_path / "sample.jpg"
    path.write_bytes(fake_jpeg(1200, 1200))

    result = validate_card_asset(path)

    assert result.valid is False
    assert "expected" in result.reason


def test_validate_card_asset_rejects_oversized_file(tmp_path: Path) -> None:
    path = tmp_path / "sample.jpg"
    path.write_bytes(fake_jpeg(padding=CARD_ART_MAX_BYTES + 1))

    result = validate_card_asset(path)

    assert result.valid is False
    assert result.size_bytes > CARD_ART_MAX_BYTES
    assert "8 MiB" in result.reason


def test_validate_card_asset_rejects_tiny_file(tmp_path: Path) -> None:
    path = tmp_path / "sample.jpg"
    path.write_bytes(fake_jpeg(padding=1))

    result = validate_card_asset(path)

    assert result.valid is False
    assert result.size_bytes < CARD_ART_MIN_BYTES
    assert "small" in result.reason


def test_validate_card_asset_accepts_jpeg_extension(tmp_path: Path) -> None:
    path = tmp_path / "sample.jpeg"
    path.write_bytes(fake_jpeg())

    result = validate_card_asset(path)

    assert result.valid is True
