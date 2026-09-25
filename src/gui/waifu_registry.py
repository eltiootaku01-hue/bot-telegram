# -*- coding: utf-8 -*-
"""Registro local de waifus y generador determinista de prompts TCG."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from bot_ia.interfaces.cafe_economy import RARITY_PRICES


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
    danbooru_tag: str = ""
    card_category: str = "Waifu / TCG"
    card_number: str = ""
    card_suit: str = ""
    lora_tags: str = ""
    card_hp: str = ""
    card_attack: str = ""
    card_type: str = ""
    prompt: str = ""
    image_path: str = ""
    assembled_path: str = ""
    progress: int = 0
    card_slots: list[CardSlot] = field(default_factory=list)


def bebida_rarity_price_menu() -> str:
    """Menú local de precios para clonación por rareza y pedido custom."""
    return (
        f"Bebida R: {RARITY_PRICES['R']} Puntos · "
        f"Bebida SR: {RARITY_PRICES['SR']} Puntos · "
        f"Bebida UR: {RARITY_PRICES['UR']} Puntos · "
        f"Bebida Especial (Custom Prompt): {RARITY_PRICES['SPECIAL']} Puntos"
    )


class WaifuRegistry:
    """Persistencia JSON local, sin WebQueue ni proveedor externo."""

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
                        danbooru_tag=str(item.get("danbooru_tag", "")).strip(),
                        personality=str(item.get("personality", "")).strip(),
                        appearance=str(item.get("appearance", "")).strip(),
                        element=str(item.get("element", "")).strip(),
                        cosplay_reference=str(
                            item.get("cosplay_reference", "")
                        ).strip(),
                        card_category=str(
                            item.get("card_category", "Waifu / TCG")
                        ).strip() or "Waifu / TCG",
                        card_number=str(item.get("card_number", "")).strip(),
                        card_suit=str(item.get("card_suit", "")).strip(),
                        lora_tags=str(item.get("lora_tags", "")).strip(),
                        card_hp=str(item.get("card_hp", "")).strip(),
                        card_attack=str(item.get("card_attack", "")).strip(),
                        card_type=str(item.get("card_type", "")).strip(),
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
    return round(
        sum(slot.progress for slot in record.card_slots)
        / len(record.card_slots)
    )


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
    category = record.card_category.strip() or "Waifu / TCG"
    lora_tags = normalize_lora_tags(record.lora_tags)
    lora_line = f"LoRA tags: {lora_tags}.\\n" if lora_tags else ""
    danbooru_line = f"Danbooru character tag: {record.danbooru_tag.strip()}.\\n" if record.danbooru_tag.strip() else ""
    card_line = ""
    if category.casefold() in {"póker", "poker", "cartas de juego"}:
        number = record.card_number.strip() or "A"
        suit = record.card_suit.strip() or "Corazones"
        card_line = f"Playing card: {number} of {suit}. Use the matching playing-card template.\\n"
    elif category.casefold() in {"waifumon / ficha de stats", "waifumon", "ficha de stats"}:
        hp = record.card_hp.strip() or "—"
        attack = record.card_attack.strip() or "—"
        card_type = record.card_type.strip() or "—"
        card_line = (
            f"Waifumon stats: HP {hp}, Attack {attack}, Element {element}, Type {card_type}. "
            "Use the matching Waifumon stats-card template.\\n"
        )
    return (
        "TCG / GAME CARD ART\\n"
        f"Category: {category}.\\n"
        f"Character: {name}.\\n"
        f"{danbooru_line}"
        f"Personality / trope: {personality}.\\n"
        f"Appearance: {appearance}.\\n"
        f"Element: {element}.\\n"
        f"Cosplay reference tier: {cosplay}.\\n"
        f"{card_line}"
        f"{lora_line}\\n"
        "Create a clean full-body character sprite suitable for a trading "
        "card game. Preserve a clear silhouette, readable costume details, "
        "expressive face, polished anime illustration, centered character, "
        "full body visible, no cropped limbs. "
        "isolated, simple white background, clean white backdrop, "
        "no scenery, no text, no logo, no watermark, no frame, "
        "no card border. The character asset must be easy to separate "
        "from the background and place inside a TCG card frame."
    )


def normalize_lora_tags(value: str) -> str:
    """Normaliza etiquetas LoRA a la forma limpia [NAME], sin inventar nombres."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    tags: list[str] = []
    for token in re.split(r"[,;\\n]+", raw):
        token = token.strip().strip("[]")
        token = re.sub(r"[^a-zA-Z0-9_.:-]+", "_", token).strip("_")
        if token:
            tags.append(f"[{token}]")
    return " ".join(dict.fromkeys(tags))


def crop_sprite_to_ratio(
    image: QImage,
    *,
    ratio: float = 3 / 4,
    background_threshold: int = 245,
    padding: float = 0.06,
) -> QImage:
    """Detecta contenido con una sonda limitada, centra el recorte y conserva proporción."""
    if image.isNull():
        return QImage()
    ratio = max(0.25, min(4.0, float(ratio)))
    source = image.convertToFormat(QImage.Format_RGBA8888)
    width, height = source.width(), source.height()

    # La detección trabaja sobre una miniatura para no bloquear la GUI con
    # millones de píxeles cuando se sube una imagen 4K o mayor.
    max_probe = 512
    scale = min(1.0, max_probe / max(width, height))
    probe = (
        source
        if scale == 1.0
        else source.scaled(
            max(1, round(width * scale)),
            max(1, round(height * scale)),
            Qt.KeepAspectRatio,
            Qt.FastTransformation,
        )
    )
    pw, ph = probe.width(), probe.height()
    left, top, right, bottom = pw, ph, -1, -1
    for y in range(ph):
        for x in range(pw):
            pixel = probe.pixel(x, y)
            alpha = (pixel >> 24) & 0xFF
            red = (pixel >> 16) & 0xFF
            green = (pixel >> 8) & 0xFF
            blue = pixel & 0xFF
            if alpha > 10 and not (
                red >= background_threshold
                and green >= background_threshold
                and blue >= background_threshold
            ):
                left, top = min(left, x), min(top, y)
                right, bottom = max(right, x), max(bottom, y)

    if right < left or bottom < top:
        left, top, right, bottom = 0, 0, pw - 1, ph - 1

    inv_scale = 1.0 / scale
    left = max(0, int(round(left * inv_scale)))
    top = max(0, int(round(top * inv_scale)))
    right = min(width - 1, int(round((right + 1) * inv_scale)) - 1)
    bottom = min(height - 1, int(round((bottom + 1) * inv_scale)) - 1)

    pad_x = max(1, int((right - left + 1) * padding))
    pad_y = max(1, int((bottom - top + 1) * padding))
    left, top = max(0, left - pad_x), max(0, top - pad_y)
    right = min(width - 1, right + pad_x)
    bottom = min(height - 1, bottom + pad_y)

    box_w, box_h = right - left + 1, bottom - top + 1
    target_w, target_h = box_w, box_h
    if box_w / box_h > ratio:
        target_h = max(1, round(box_w / ratio))
    else:
        target_w = max(1, round(box_h * ratio))

    # Si el recuadro requerido supera la imagen, se limita sin deformarla.
    target_w = min(target_w, width)
    target_h = min(target_h, height)
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    left = max(0, min(width - target_w, round(center_x - target_w / 2)))
    top = max(0, min(height - target_h, round(center_y - target_h / 2)))
    return source.copy(left, top, target_w, target_h)

def frame_candidates(root: Path, rarity: str, element: str) -> list[Path]:
    """Devuelve marcos elemento-específicos y el fallback por rareza."""
    rarity = rarity.strip().upper()
    element_slug = slugify(element).casefold()
    frame_dir = Path(root) / "assets" / "tcg_frames"
    if rarity == "R":
        # R es deliberadamente neutra: la ficha base no debe heredar colores elementales.
        return [
            frame_dir / "frame_R.svg",
            frame_dir / "frame_R.png",
        ]
    if rarity == "UR":
        # UR usa el marco dorado común; el elemento se resalta en el renderizador.
        return [
            frame_dir / "frame_UR.svg",
            frame_dir / "frame_UR.png",
            frame_dir / f"frame_UR_{element_slug}.svg",
            frame_dir / f"frame_UR_{element_slug}.png",
        ]
    return [
        frame_dir / f"frame_{rarity}_{element_slug}.svg",
        frame_dir / f"frame_{rarity}_{element_slug}.png",
        frame_dir / f"frame_{rarity}.svg",
        frame_dir / f"frame_{rarity}.png",
    ]


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    return value.strip("_") or "waifu"
