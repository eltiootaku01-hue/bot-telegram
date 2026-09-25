# -*- coding: utf-8 -*-
"""Flujo local de pedidos «Bebida Especial» y autocompletado de personajes."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
import unicodedata
from typing import Iterable

from .cafe_economy import ORDER_COST_HIGH, ORDER_COST_NORMAL, OrderQuote, quote_bebida_order



EXPOSURE_LEVELS = ("SFW", "Sugerente", "NSFW")
BOLDNESS_LEVELS = ("Suave", "Atrevido", "Máximo")
PRODUCT_TYPES = ("Carta TCG", "Naipe", "Waifumon")
DEFAULT_POSES = ("De pie", "Acción dinámica", "Retrato", "Pose cosplay")
DEFAULT_OUTFITS = ("Uniforme", "Casual", "Fantasia", "Cosplay")


@dataclass(frozen=True, slots=True)
class BebidaOrder:
    """Pedido estructurado; no genera contenido por sí mismo."""

    character: str = ""
    character_tag: str = ""
    exposure: str = "SFW"
    boldness: str = "Suave"
    pose: str = "De pie"
    outfit: str = "Casual"
    cosplay: str = ""
    product_type: str = "Carta TCG"

    def normalized(self) -> "BebidaOrder":
        exposure = self.exposure if self.exposure in EXPOSURE_LEVELS else "SFW"
        boldness = self.boldness if self.boldness in BOLDNESS_LEVELS else "Suave"
        product = self.product_type if self.product_type in PRODUCT_TYPES else "Carta TCG"
        return replace(
            self,
            character=self.character.strip(),
            character_tag=normalize_danbooru_tag(self.character_tag or self.character),
            exposure=exposure,
            boldness=boldness,
            pose=self.pose.strip() or "De pie",
            outfit=self.outfit.strip() or "Casual",
            cosplay=self.cosplay.strip(),
            product_type=product,
        )


def normalize_danbooru_tag(value: str) -> str:
    """Convierte nombres locales a tag seguro; no inventa el sitio/fandom."""
    value = str(value or "").strip()
    if not value:
        return ""
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^A-Za-z0-9_()'\-]+", "", value)
    return value.lower()


def character_suggestions(records: Iterable[object], query: str = "") -> list[str]:
    """Sugerencias deterministas desde el registro local, sin red ni tags inventados."""
    query = normalize_danbooru_tag(query)
    candidates: list[str] = []
    for record in records:
        name = record.name.strip()
        tag = str(getattr(record, "danbooru_tag", "")).strip()
        for value in (name, tag):
            if value and value not in candidates:
                candidates.append(value)
    if not query:
        return candidates[:30]
    return [
        value for value in candidates
        if query in normalize_danbooru_tag(value)
    ][:30]


def build_bebida_summary(order: BebidaOrder) -> str:
    """Resumen textual para GUI/bot. Mantiene el nivel elegido como metadata."""
    item = order.normalized()
    return (
        "🥤 BEBIDA ESPECIAL · CAMI\n"
        f"Personaje: {item.character or '(sin seleccionar)'}\n"
        f"Tag: {item.character_tag or '(sin tag local)'}\n"
        f"Exposición: {item.exposure}\n"
        f"Atrevimiento: {item.boldness}\n"
        f"Pose: {item.pose}\n"
        f"Vestimenta: {item.outfit}\n"
        f"Cosplay: {item.cosplay or 'No especificado'}\n"
        f"Producto: {item.product_type}"
    )


def build_bebida_prompt(order: BebidaOrder) -> str:
    """Prepara metadata para el pipeline de arte; no añade contenido sexual."""
    item = order.normalized()
    return (
        "BOT-IA · PEDIDO BEBIDA ESPECIAL\n"
        f"Character: {item.character}.\n"
        f"Character tag: {item.character_tag}.\n"
        f"Exposure tier: {item.exposure}.\n"
        f"Boldness level: {item.boldness}.\n"
        f"Pose: {item.pose}.\n"
        f"Outfit: {item.outfit}.\n"
        f"Cosplay: {item.cosplay or 'none'}.\n"
        f"Product type: {item.product_type}.\n"
        "Use the selected metadata exactly; do not invent character identity."
    )


class BebidaOrderFlow:
    """Estado mínimo por usuario para el asistente interactivo de Telegram."""

    def __init__(self) -> None:
        self._orders: dict[str, BebidaOrder] = {}

    def start(self, user_id: str, character: str = "") -> BebidaOrder:
        order = BebidaOrder(character=character.strip())
        self._orders[str(user_id)] = order
        return order

    def get(self, user_id: str) -> BebidaOrder:
        return self._orders.setdefault(str(user_id), BebidaOrder())

    def choose(self, user_id: str, field: str, value: str) -> BebidaOrder:
        current = self.get(user_id)
        allowed = {
            "exposure": EXPOSURE_LEVELS,
            "boldness": BOLDNESS_LEVELS,
            "product_type": PRODUCT_TYPES,
        }
        values = allowed.get(field)
        if values is None or value not in values:
            return current
        updated = replace(current, **{field: value})
        self._orders[str(user_id)] = updated
        return updated

    def set_character(self, user_id: str, character: str, tag: str = "") -> BebidaOrder:
        updated = replace(self.get(user_id), character=character.strip(), character_tag=tag.strip())
        self._orders[str(user_id)] = updated
        return updated

    def clear(self, user_id: str) -> None:
        self._orders.pop(str(user_id), None)

def bebida_order_quote(order: BebidaOrder, *, existing_character: bool, points: int) -> OrderQuote:
    """Cotiza clonación local vs. carta personalizada sin usar red."""
    item = order.normalized()
    _ = item
    return quote_bebida_order(existing=existing_character, points=points)


def bebida_price_text() -> str:
    return (
        "☕ Puntos del Café: "
        f"clonación existente = {ORDER_COST_NORMAL}; "
        f"carta personalizada = {ORDER_COST_HIGH}."
    )

