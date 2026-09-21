from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


CARD_ART_WIDTH = 1024
CARD_ART_HEIGHT = 1536
CARD_ART_MAX_BYTES = 8 * 1024 * 1024
CARD_ART_EXTENSION = ".jpg"
CARD_ART_EXTENSIONS = frozenset({".jpg", ".jpeg"})
CARD_ART_MIN_BYTES = 50 * 1024


@dataclass(frozen=True, slots=True)
class CardAssetValidation:
    valid: bool
    width: int | None
    height: int | None
    size_bytes: int
    reason: str


def card_asset_path(character_id: str, variant: str = "normal") -> str:
    safe_id = character_id.strip()
    safe_variant = variant.strip().casefold()
    if not safe_id or "/" in safe_id or "\\" in safe_id:
        raise ValueError("character_id must be a safe asset identifier")
    if safe_variant not in {"normal", "shiny"}:
        raise ValueError("variant must be normal or shiny")
    return f"assets/production/cards/{safe_id}--{safe_variant}{CARD_ART_EXTENSION}"


def jpeg_dimensions(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None

    index = 2
    sof_markers = {
        0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
        0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
    }
    while index < len(data):
        while index < len(data) and data[index] != 0xFF:
            index += 1
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            return None

        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA:
            return None
        if index + 2 > len(data):
            return None

        segment_length = int.from_bytes(data[index:index + 2], "big")
        if segment_length < 2 or index + segment_length > len(data):
            return None

        if marker in sof_markers and segment_length >= 7:
            height = int.from_bytes(data[index + 3:index + 5], "big")
            width = int.from_bytes(data[index + 5:index + 7], "big")
            return width, height

        index += segment_length

    return None


def validate_card_asset(path: Path) -> CardAssetValidation:
    if not path.is_file():
        return CardAssetValidation(False, None, None, 0, "file does not exist")

    size = path.stat().st_size
    if path.suffix.casefold() not in CARD_ART_EXTENSIONS:
        return CardAssetValidation(False, None, None, size, "asset must be JPG/JPEG")
    if size > CARD_ART_MAX_BYTES:
        return CardAssetValidation(False, None, None, size, "asset exceeds 8 MiB")
    if size < CARD_ART_MIN_BYTES:
        return CardAssetValidation(False, None, None, size, "asset is unexpectedly small")

    dimensions = jpeg_dimensions(path)
    if dimensions is None:
        return CardAssetValidation(False, None, None, size, "invalid JPEG or dimensions unreadable")
    width, height = dimensions
    if (width, height) != (CARD_ART_WIDTH, CARD_ART_HEIGHT):
        return CardAssetValidation(
            False,
            width,
            height,
            size,
            f"expected {CARD_ART_WIDTH}x{CARD_ART_HEIGHT}, got {width}x{height}",
        )

    return CardAssetValidation(True, width, height, size, "ok")
