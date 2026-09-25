# -*- coding: utf-8 -*-
"""Registro local de waifus y generador determinista de prompts TCG."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re


@dataclass(slots=True)
class CardSlot:
    """Estado de una carta individual del tracker."""

    name: str
    rarity: str
    image_path: str = ""
    assembled_path: str = ""
    complete: bool = False

    @property
    def progress(self) -> int:
        return 100 if self.complete else (50 if self.image_path else 0)


@dataclass(slots=True)
class WaifuRecord:
    """Ficha local de una waifu preparada para una carta TCG."""

    name: str
    personality: str
    appearance: str
    element: str
    cosplay_reference: str
    prompt: str = ""
    image_path: str = ""
    assembled_path: str = ""
    progress: int = 0
    card_slots: list[CardSlot] = field(default_factory=list)


class WaifuRegistry:
    """Persistencia JSON local, sin WebQueue ni proveedor externo."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.path = self.root / "config" / "waifu_registry.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[WaifuRecord]:
        if not self.path.is_file():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        records: list[WaifuRecord] = []
        for item in payload:
            if isinstance(item, dict) and str(item.get("name", "")).strip():
                records.append(
                    WaifuRecord(
                        name=str(item.get("name", "")).strip(),
                        personality=str(item.get("personality", "")).strip(),
                        appearance=str(item.get("appearance", "")).strip(),
                        element=str(item.get("element", "")).strip(),
                        cosplay_reference=str(
                            item.get("cosplay_reference", "")
                        ).strip(),
                        prompt=str(item.get("prompt", "")).strip(),
                        image_path=str(item.get("image_path", "")).strip(),
                        assembled_path=str(
                            item.get("assembled_path", "")
                        ).strip(),
                        progress=max(
                            0,
                            min(
                                100,
                                _safe_progress(item.get("progress", 0)),
                            ),
                        ),
                        card_slots=_load_slots(item.get("card_slots")),
                    )
                )
        return records

def _load_slots(value: object) -> list[CardSlot]:
    defaults = [
        CardSlot("Carta 1", "R"),
        CardSlot("Carta 2", "SR"),
        CardSlot("Cosplay UR", "UR"),
    ]
    if not isinstance(value, list):
        return defaults
    result: list[CardSlot] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        rarity = str(item.get("rarity", "R")).strip().upper()
        if name and rarity in {"R", "SR", "UR"}:
            result.append(
                CardSlot(
                    name=name,
                    rarity=rarity,
                    image_path=str(item.get("image_path", "")).strip(),
                    assembled_path=str(
                        item.get("assembled_path", "")
                    ).strip(),
                    complete=bool(item.get("complete", False)),
                )
            )
    return result or defaults


def _ensure_slots(record: WaifuRecord) -> None:
    if not record.card_slots:
        record.card_slots = [
            CardSlot("Carta 1", "R"),
            CardSlot("Carta 2", "SR"),
            CardSlot("Cosplay UR", "UR"),
        ]


def record_progress(record: WaifuRecord) -> int:
    _ensure_slots(record)
    return round(sum(slot.progress for slot in record.card_slots) / len(record.card_slots))


    def save(self, records: list[WaifuRecord]) -> None:
        for record in records:
            _ensure_slots(record)
            record.progress = record_progress(record)
        payload = [asdict(record) for record in records]
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


def _safe_progress(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def generate_tcg_prompt(record: WaifuRecord) -> str:
    """Construye un prompt consistente y separado del trabajo de composición."""

    name = record.name.strip() or "original anime character"
    personality = record.personality.strip() or "distinctive personality"
    appearance = record.appearance.strip() or "detailed character appearance"
    element = record.element.strip() or "fantasy"
    cosplay = record.cosplay_reference.strip() or "SR"
    return (
        "TCG CHARACTER SPRITE / WAIFU CARD ART\n"
        f"Character: {name}.\n"
        f"Personality / trope: {personality}.\n"
        f"Appearance: {appearance}.\n"
        f"Element: {element}.\n"
        f"Cosplay reference tier: {cosplay}.\n\n"
        "Create a clean full-body character sprite suitable for a trading "
        "card game. Preserve a clear silhouette, readable costume details, "
        "expressive face, polished anime illustration, centered character, "
        "full body visible, no cropped limbs. "
        "isolated, simple white background, clean white backdrop, "
        "no scenery, no text, no logo, no watermark, no frame, "
        "no card border. The character asset must be easy to separate "
        "from the background and place inside a TCG card frame."
    )


def frame_candidates(root: Path, rarity: str, element: str) -> list[Path]:
    """Devuelve marcos elemento-específicos y el fallback por rareza."""
    rarity = rarity.strip().upper()
    element_slug = slugify(element).casefold()
    frame_dir = Path(root) / "assets" / "tcg_frames"
    return [
        frame_dir / f"frame_{rarity}_{element_slug}.svg",
        frame_dir / f"frame_{rarity}_{element_slug}.png",
        frame_dir / f"frame_{rarity}.svg",
        frame_dir / f"frame_{rarity}.png",
    ]


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    return value.strip("_") or "waifu"
