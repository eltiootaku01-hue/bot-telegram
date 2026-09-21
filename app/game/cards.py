from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum

from app.game.models import CardTier, Character


class CardVariant(StrEnum):
    NORMAL = "normal"
    SHINY = "shiny"


class ShinyOutfit(StrEnum):
    WORK_UNIFORM = "uniforme_de_trabajo"
    ANIMAL = "traje_animal"
    COSPLAY = "cosplay"
    CAFE_PREMIUM = "uniforme_cafe_premium"
    FESTIVAL = "festival"
    IDOL = "idol"
    DETECTIVE = "detective"
    BATTLE_DRESS = "battle_dress"
    WINTER_FORMAL = "formal_de_invierno"
    SUMMER_RESORT = "resort_de_verano"


class NormalOutfit(StrEnum):
    CANON_INSPIRED = "look_base"
    CASUAL = "casual"
    ADVENTURE = "aventura"
    ATHLETIC = "deportivo"
    FORMAL = "formal"
    CAFE = "cafe"


@dataclass(frozen=True, slots=True)
class WaifuCard:
    """Concrete collectible card instance resolved deterministically from a seed."""

    card_id: str
    character_id: str
    name: str
    anime: str
    tier: CardTier
    variant: CardVariant
    outfit: str
    fusion_of: tuple[str, str] = ()
    mature_art_allowed: bool = False

    @property
    def is_fusion(self) -> bool:
        return self.tier is CardTier.UR and len(self.fusion_of) == 2


SHINY_CHANCE_DENOMINATOR = 8
NORMAL_OUTFITS = tuple(item.value for item in NormalOutfit) + (
    "uniforme_de_verano",
    "look_callejero",
    "look_academia",
    "look_invernal",
)
SHINY_OUTFITS = tuple(item.value for item in ShinyOutfit) + (
    "cosplay_heroina",
    "cosplay_detective",
    "traje_orejas_gatunas",
    "traje_zorrita",
    "uniforme_medico",
    "uniforme_cocinera",
    "uniforme_mecanica",
    "uniforme_reportera",
)


def _digest(seed: str) -> bytes:
    return hashlib.sha256(seed.encode("utf-8")).digest()


def _variant_for_seed(seed: str) -> CardVariant:
    digest = _digest(seed)
    return (
        CardVariant.SHINY
        if digest[0] % SHINY_CHANCE_DENOMINATOR == 0
        else CardVariant.NORMAL
    )


def _outfit_for_seed(seed: str, variant: CardVariant) -> str:
    digest = _digest(f"{seed}:outfit")
    pool = SHINY_OUTFITS if variant is CardVariant.SHINY else NORMAL_OUTFITS
    return pool[int.from_bytes(digest[:8], "big") % len(pool)]


def card_for_character(
    character: Character,
    *,
    seed: str,
    mature_art_allowed: bool = False,
) -> WaifuCard:
    variant = _variant_for_seed(seed)
    outfit = _outfit_for_seed(seed, variant)
    card_id = f"{character.id}:{character.card_tier.value}:{variant.value}:{outfit}"
    return WaifuCard(
        card_id=card_id,
        character_id=character.id,
        name=character.name,
        anime=character.anime,
        tier=character.card_tier,
        variant=variant,
        outfit=outfit,
        mature_art_allowed=mature_pair and variant is CardVariant.SHINY,
    )


def fusion_card_for_characters(
    first: Character,
    second: Character,
    *,
    seed: str,
    mature_art_allowed: bool = False,
) -> WaifuCard:
    if first.id == second.id:
        raise ValueError("UR fusion requires two different waifus")
    mature_pair = (
        mature_art_is_approved(first.id)
        and mature_art_is_approved(second.id)
    )
    parents = tuple(sorted((first.id, second.id)))
    variant = _variant_for_seed(seed)
    outfit = _outfit_for_seed(seed, variant)
    card_id = f"ur-fusion:{parents[0]}+{parents[1]}:{variant.value}:{outfit}"
    return WaifuCard(
        card_id=card_id,
        character_id=f"fusion:{parents[0]}+{parents[1]}",
        name=f"{first.name} × {second.name}",
        anime=f"{first.anime} × {second.anime}",
        tier=CardTier.UR,
        variant=variant,
        outfit=outfit,
        fusion_of=parents,
        mature_art_allowed=mature_art_allowed and variant is CardVariant.SHINY,
    )


def generic_r_card(seed: str) -> WaifuCard:
    """Generate an original R-rarity generic waifu card without polluting the IP catalog."""
    digest = _digest(seed)
    archetypes = (
        "barista aventurera",
        "exploradora urbana",
        "mecánica de taller",
        "bibliotecaria nocturna",
        "fotógrafa viajera",
        "chef de festival",
        "mensajera felina",
        "detective de barrio",
        "artista callejera",
        "piloto de carreras",
        "jardinera de invernadero",
        "guardiana del acuario",
    )
    colors = (
        "azul petróleo",
        "coral",
        "violeta",
        "verde menta",
        "rojo vino",
        "dorado",
        "turquesa",
        "lavanda",
    )
    archetype = archetypes[digest[0] % len(archetypes)]
    accent = colors[digest[1] % len(colors)]
    token = digest.hex()[:10]
    return WaifuCard(
        card_id=f"generic-r:{token}",
        character_id=f"generic-r:{token}",
        name=f"Waifu R-{token.upper()}",
        anime="Ciudad Animals — original",
        tier=CardTier.R,
        variant=CardVariant.NORMAL,
        outfit=f"{archetype} · acento {accent}",
    )


def card_variants_for(character: Character) -> tuple[WaifuCard, ...]:
    """Return a compact deterministic preview of the first 16 visual variants."""
    return tuple(
        card_for_character(
            character,
            seed=f"{character.id}:preview:{index}",
        )
        for index in range(16)
    )
