# -*- coding: utf-8 -*-
"""Flujo local de pedidos «Bebida Especial» y autocompletado de personajes."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
import unicodedata
from typing import Iterable

from .cafe_economy import ORDER_COST_HIGH, ORDER_COST_NORMAL, RARITY_PRICES, OrderQuote, quote_bebida_order
from .hardening import sanitize_control_text, whitelist_tag



EXPOSURE_LEVELS = ("SFW", "Sugerente", "NSFW")
BOLDNESS_LEVELS = ("Suave", "Atrevido", "Máximo")
PRODUCT_TYPES = ("Carta TCG", "Naipe", "Waifumon", "Imagen IA Personalizada")
DEFAULT_POSES = ("De pie", "Acción dinámica", "Retrato", "Pose cosplay")
DEFAULT_OUTFITS = ("Uniforme", "Casual", "Fantasia", "Cosplay")

RESOLUTIONS = {
    "XL": "1104x1824",
    "L": "944x1584",
    "M": "768x1280",
}
RENDER_STYLES = {
    "Classic Anime": "classic anime style, cel shaded",
    "Retro Glam Anime": "retro glam anime, 90s anime aesthetic",
    "Modern Glam Anime": "modern glam anime, detailed shading, soft lighting",
    "Hyper Pop": "hyper pop style, neon lines, vibrant colors",
}


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
    resolution: str = "L"
    render_style: str = "Classic Anime"

    def normalized(self) -> "BebidaOrder":
        exposure = self.exposure if self.exposure in EXPOSURE_LEVELS else "SFW"
        boldness = self.boldness if self.boldness in BOLDNESS_LEVELS else "Suave"
        product = self.product_type if self.product_type in PRODUCT_TYPES else "Carta TCG"
        resolution = self.resolution if self.resolution in RESOLUTIONS else "L"
        render_style = self.render_style if self.render_style in RENDER_STYLES else "Classic Anime"
        return replace(
            self,
            character=sanitize_control_text(self.character, max_length=128),
            character_tag=normalize_danbooru_tag(self.character_tag or self.character),
            exposure=exposure,
            boldness=boldness,
            pose=sanitize_free_text(self.pose) or "De pie",
            outfit=sanitize_free_text(self.outfit) or "Casual",
            cosplay=sanitize_free_text(self.cosplay)[:128],
            product_type=product,
            resolution=resolution,
            render_style=render_style,
        )


def normalize_danbooru_tag(value: str) -> str:
    """Normaliza sintaxis de tag; la whitelist se aplica por separado."""
    value = sanitize_control_text(value, max_length=128)
    if not value:
        return ""
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^A-Za-z0-9_()'\-]+", "", value)
    return value.lower()


def sanitize_free_text(value: str, *, max_length: int = 128) -> str:
    """Sanitiza texto libre sin permitir caracteres de control."""
    return sanitize_control_text(value, max_length=max_length)


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
        f"Producto: {item.product_type}\n"
        f"Resolución: {item.resolution} ({RESOLUTIONS[item.resolution]})\n"
        f"Estilo: {item.render_style}"
    )


def build_bebida_prompt(order: BebidaOrder) -> str:
    """Prepara metadata para el pipeline de arte; no añade contenido sexual."""
    item = order.normalized()
    return (
        "BOT-IA · SPECIAL DRINK IMAGE ORDER\n"
        f"Character: {item.character}.\n"
        f"Character tag: {item.character_tag}.\n"
        f"Exposure tier: {item.exposure}.\n"
        f"Boldness level: {item.boldness}.\n"
        f"Pose: {item.pose}.\n"
        f"Outfit: {item.outfit}.\n"
        f"Cosplay: {item.cosplay or 'none'}.\n"
        f"Product type: {item.product_type}.\n"
        f"Resolution: {item.resolution} ({RESOLUTIONS[item.resolution]}).\n"
        f"Rendering style: {RENDER_STYLES[item.render_style]}.\n"
        "simple white background, isolated.\n"
        "Use the selected metadata exactly; do not invent character identity."
    )


class BebidaOrderFlow:
    """Estado mínimo por usuario para el asistente interactivo de Telegram."""

    def __init__(self, allowed_tags: Iterable[str] = ()) -> None:
        self._orders: dict[str, BebidaOrder] = {}
        self._allowed_tags = tuple(
            tag.strip()
            for tag in allowed_tags
            if str(tag).strip()
        )

    def _resolve_tag(self, value: str) -> str:
        return whitelist_tag(value, self._allowed_tags)

    def start(self, user_id: str, character: str = "") -> BebidaOrder:
        order = BebidaOrder()
        self._orders[str(user_id)] = order
        if character:
            self.set_character(user_id, character)
        return self.get(user_id)

    def get(self, user_id: str) -> BebidaOrder:
        return self._orders.setdefault(str(user_id), BebidaOrder())

    def choose(self, user_id: str, field: str, value: str) -> BebidaOrder:
        current = self.get(user_id)
        allowed = {
            "exposure": EXPOSURE_LEVELS,
            "boldness": BOLDNESS_LEVELS,
            "product_type": PRODUCT_TYPES,
            "resolution": tuple(RESOLUTIONS),
            "render_style": tuple(RENDER_STYLES),
        }
        values = allowed.get(field)
        if values is None or value not in values:
            return current
        updated = replace(current, **{field: value})
        self._orders[str(user_id)] = updated
        return updated

    def set_character(self, user_id: str, character: str, tag: str = "") -> BebidaOrder:
        safe_character = sanitize_control_text(character, max_length=128)
        resolved_tag = self._resolve_tag(tag or safe_character)
        if not resolved_tag:
            return self.get(user_id)
        updated = replace(
            self.get(user_id),
            character=safe_character,
            character_tag=resolved_tag,
        ).normalized()
        self._orders[str(user_id)] = updated
        return updated

    def clear(self, user_id: str) -> None:
        self._orders.pop(str(user_id), None)

def bebida_order_quote(order: BebidaOrder, *, existing_character: bool, points: int, target_rarity: str | None = None) -> OrderQuote:
    """Cotiza la rareza exacta de la carta objetivo, sin usar red."""
    item = order.normalized()
    _ = item
    return quote_bebida_order(
        existing=existing_character,
        target_rarity=target_rarity,
        points=points,
    )


def bebida_price_text() -> str:
    return (
        "☕ Puntos del Café: "
        f"R = {ORDER_COST_NORMAL}; "
        f"SR = {RARITY_PRICES['SR']}; "
        f"UR = {RARITY_PRICES['UR']}; "
        f"Especial = {RARITY_PRICES['SPECIAL']}."
    )

