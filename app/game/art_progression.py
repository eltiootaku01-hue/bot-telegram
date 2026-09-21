from __future__ import annotations

from dataclasses import dataclass

from app.game.models import CardTier


@dataclass(frozen=True, slots=True)
class ArtStage:
    min_level: int
    max_level: int
    style: str
    outfit: str
    framing: str


SAFE_ART_STAGES: tuple[ArtStage, ...] = (
    ArtStage(1, 5, "chibi", "ropa cotidiana del Café", "retrato de cabeza y hombros"),
    ArtStage(6, 10, "anime", "ropa cotidiana del personaje", "medio cuerpo"),
    ArtStage(11, 15, "anime", "atuendo temático reforzado", "cuerpo completo"),
    ArtStage(16, 20, "anime premium", "vestuario especial de evento", "cuerpo completo con efectos"),
    ArtStage(21, 25, "anime premium", "vestuario de forma final", "ilustración completa"),
)


CARD_OUTFITS: dict[CardTier, str] = {
    CardTier.R: "versión base",
    CardTier.SR: "versión especial de profesión o evento",
    CardTier.UR: "versión ultra con escenario y efectos exclusivos",
}


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
) -> str:
    """Return a deterministic prompt specification for future image tooling."""
    stage = art_stage_for_level(level)
    special = CARD_OUTFITS[card_tier]
    return (
        f"Character: {character_name}. Source work: {anime}. "
        f"Style: {stage.style}. Framing: {stage.framing}. "
        f"Costume: {stage.outfit}; {special}. "
        "Game illustration, polished anime art, coherent character identity, "
        "clear silhouette, readable face, expressive pose, clean background."
    )
