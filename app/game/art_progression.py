from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.game.models import CardTier


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
    ArtStage(1, 5, "anime base", "ropa cotidiana del personaje", "según la carta"),
    ArtStage(6, 10, "anime", "ropa cotidiana reforzada", "según la carta"),
    ArtStage(11, 15, "anime premium", "vestuario temático de evento", "según la carta"),
    ArtStage(16, 20, "anime premium", "vestuario especial del personaje", "según la carta"),
    ArtStage(21, 25, "anime premium", "vestuario de forma avanzada", "según la carta"),
)


CARD_OUTFITS: dict[CardTier, str] = {
    CardTier.R: "versión base",
    CardTier.SR: "versión especial de profesión o evento",
    CardTier.UR: "versión ultra con escenario y efectos exclusivos",
}


def card_art_tier(popularity_score: int, power_score: int) -> CardArtTier:
    """Derive the four visual bands without changing gameplay CardTier."""
    if not 0 <= popularity_score <= 100 or not 0 <= power_score <= 100:
        raise ValueError("art scores must be between 0 and 100")
    combined = (popularity_score + power_score) / 2
    if combined >= 78:
        return CardArtTier.UR
    if combined >= 52:
        return CardArtTier.SR
    if combined >= 40:
        return CardArtTier.S
    return CardArtTier.R


def art_frame_for(*, popularity_score: int, power_score: int) -> ArtFrameRule:
    return CARD_ART_RULES[card_art_tier(popularity_score, power_score)]


def art_stage_for_level(level: int) -> ArtStage:
    if not 1 <= level <= 25:
        raise ValueError("art level must be between 1 and 25")
    return next(
        stage for stage in SAFE_ART_STAGES
        if stage.min_level <= level <= stage.max_level
    )


def art_prompt_spec(
    *,
    character_name: str,
    anime: str,
    level: int,
    card_tier: CardTier,
    popularity_score: int = 50,
    power_score: int = 50,
    unique_direction: str = "",
) -> str:
    """Return deterministic, safe art direction for a future image provider."""
    stage = art_stage_for_level(level)
    frame = art_frame_for(
        popularity_score=popularity_score,
        power_score=power_score,
    )
    special = CARD_OUTFITS[card_tier]
    direction = unique_direction.strip() or "diseño visual propio del personaje"
    return (
        f"Character: {character_name}. Source work: {anime}. "
        f"Visual tier: {frame.tier.value}. Visible composition: {frame.visible_percent}. "
        f"Framing: {frame.framing}. Pose: {frame.pose_direction}. "
        f"Style: {stage.style}. Costume: {stage.outfit}; {special}. "
        f"Unique direction: {direction}. "
        "Original polished anime fantasy illustration, expressive hand-drawn linework, "
        "controlled cel shading, rich but coherent lighting, distinct silhouette, "
        "detailed eyes/hair/clothing, non-photorealistic, safe-for-work, "
        "do not copy another artist's exact style."
    )
