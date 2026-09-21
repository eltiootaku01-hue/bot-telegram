from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.game.art_directions import direction_for
from app.game.models import CardTier, Rarity
from app.game.waifumon_progression import evolution_band_for_level


class CardArtTier(StrEnum):
    """Visual presentation tier; independent from combat rarity."""

    R = "R"
    S = "S"
    SR = "SR"
    UR = "UR"


@dataclass(frozen=True, slots=True)
class ArtFrameRule:
    tier: CardArtTier
    visible_percent: str
    framing: str
    pose_direction: str
    finish: str


CARD_ART_RULES: dict[CardArtTier, ArtFrameRule] = {
    CardArtTier.R: ArtFrameRule(
        CardArtTier.R,
        "20%",
        "rostro + una pequeña parte de hombros",
        "expresión clara, pose mínima y centrada",
        "acabado limpio, detallado en rostro y cabello",
    ),
    CardArtTier.S: ArtFrameRule(
        CardArtTier.S,
        "40%",
        "cabeza, hombros y torso superior hasta el pecho",
        "pose que refuerce personalidad, oficio o elemento",
        "acabado anime pulido con iluminación selectiva",
    ),
    CardArtTier.SR: ArtFrameRule(
        CardArtTier.SR,
        "60-80%",
        "medio cuerpo amplio hasta cintura o muslos según composición",
        "pose dinámica y escenográfica, con accesorios narrativos",
        "ilustración premium, iluminación y fondo trabajado",
    ),
    CardArtTier.UR: ArtFrameRule(
        CardArtTier.UR,
        "100%+",
        "cuerpo completo y composición abierta",
        "pose heroica o icónica que defina al avatar",
        "acabado premium impecable, efectos, profundidad y fondo completo",
    ),
}


@dataclass(frozen=True, slots=True)
class ArtStage:
    min_level: int
    max_level: int
    style: str
    outfit: str
    framing: str


SAFE_ART_STAGES: tuple[ArtStage, ...] = (
    ArtStage(1, 5, "chibi", "ropa cotidiana del personaje", "según la carta"),
    ArtStage(6, 10, "anime", "ropa cotidiana reforzada", "según la carta"),
    ArtStage(11, 20, "anime premium", "vestuario especial de evolución", "según la carta"),
    ArtStage(21, 30, "anime premium", "vestuario final de evolución", "según la carta"),
)


WAIFUMON_RARITY_ART_VISIBILITY: dict[Rarity, str] = {
    Rarity.D: "15%",
    Rarity.C: "20%",
    Rarity.B: "30%",
    Rarity.A: "45%",
    Rarity.S: "60%",
    Rarity.SS: "80%",
    Rarity.SSS: "100%",
}


def waifumon_rarity_art_visibility(rarity: Rarity | str) -> str:
    resolved = rarity if isinstance(rarity, Rarity) else Rarity(rarity)
    return WAIFUMON_RARITY_ART_VISIBILITY[resolved]


CARD_OUTFITS: dict[CardTier, str] = {
    CardTier.R: "versión base",
    CardTier.S: "variante destacada de profesión o evento",
    CardTier.SR: "versión premium especial de profesión o evento",
    CardTier.UR: "versión ultra con escenario, pose y efectos exclusivos",
}


def card_art_tier(card_tier: CardTier) -> CardArtTier:
    """Map the explicit card tier to its matching visual presentation tier."""
    if card_tier is CardTier.R:
        return CardArtTier.R
    if card_tier is CardTier.S:
        return CardArtTier.S
    if card_tier is CardTier.SR:
        return CardArtTier.SR
    if card_tier is CardTier.UR:
        return CardArtTier.UR
    raise ValueError(f"unsupported card tier: {card_tier!r}")


def art_frame_for(*, card_tier: CardTier) -> ArtFrameRule:
    return CARD_ART_RULES[card_art_tier(card_tier)]


def art_stage_for_level(level: int) -> ArtStage:
    if not 1 <= level <= 30:
        raise ValueError("art level must be between 1 and 30")
    return next(
        stage for stage in SAFE_ART_STAGES
        if stage.min_level <= level <= stage.max_level
    )


def art_prompt_spec(
    *,
    character_name: str,
    anime: str,
    character_id: str = "",
    level: int,
    card_tier: CardTier,
    variant: str = "normal",
    popularity_score: int = 50,
    power_score: int = 50,
    unique_direction: str = "",
    mature_art_allowed: bool = False,
) -> str:
    """Return deterministic, safe art direction for a future image provider."""
    stage = art_stage_for_level(level)
    frame = art_frame_for(card_tier=card_tier)
    special = CARD_OUTFITS[card_tier]
    if variant.casefold() not in {"normal", "shiny"}:
        raise ValueError("variant must be normal or shiny")
    if variant.casefold() == "shiny" and mature_art_allowed:
        sensuality = "ecchi elegante y adulto, sugestivo pero no explícito, ropa completamente opaca"
    elif variant.casefold() == "shiny":
        sensuality = "vestuario especial atractivo pero totalmente no explícito y apropiado"
    else:
        sensuality = "vestuario normal completamente vestido, atractivo y aventurero"
    evolution_band = evolution_band_for_level(level)
    direction = unique_direction.strip() or "diseño visual propio del personaje"
    direction_key = character_id.strip().casefold() or character_name.casefold().replace(" ", "-")
    visual = direction_for(direction_key)
    return (
        f"Character: {character_name}. Source work: {anime}. "
        f"Visual tier: {frame.tier.value}. Visible composition: {frame.visible_percent}. "
        f"Framing: {frame.framing}. Pose: {frame.pose_direction}. "
        f"WaifuMon evolution stage: {evolution_band.stage.value}. "
        f"Evolution design language: {evolution_band.design_language}. "
        f"Evolution framing: {evolution_band.framing}. "
        f"Style: {stage.style}. Costume: {stage.outfit}; {special}. "
        f"Variant: {variant.casefold()}. Visual safety: {sensuality}. "
        f"Design change requirement: evolution stage {evolution_band.stage.value} must be visually distinct from the previous stage through costume, pose, silhouette, accessories and lighting; do not merely crop or recolor the previous art. " 
        f"Unique direction: {direction}. " 
        f"Palette: {visual.palette}; "
        f"Expression: {visual.expression}; "
        f"Pose: {visual.pose}; "
        f"Environment: {visual.environment}; "
        f"Motif: {visual.motif}. "
        "Original polished anime fantasy illustration, expressive hand-drawn linework, "
        "controlled cel shading, rich but coherent lighting, distinct silhouette, "
        "detailed eyes/hair/clothing, non-photorealistic, safe-for-work, "
        "do not copy another artist's exact style."
    )
