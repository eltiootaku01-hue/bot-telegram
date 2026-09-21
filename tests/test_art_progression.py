import pytest

from app.game.art_progression import (
    CARD_ART_RULES,
    CARD_OUTFITS,
    CardArtTier,
    art_frame_for,
    art_prompt_spec,
    art_stage_for_level,
    card_art_tier,
)
from app.game.models import CardTier


@pytest.mark.parametrize(
    ("score", "tier", "visible"),
    [
        (30, CardArtTier.R, "20%"),
        (40, CardArtTier.S, "40%"),
        (51, CardArtTier.S, "40%"),
        (52, CardArtTier.SR, "60-80%"),
        (77, CardArtTier.SR, "60-80%"),
        (78, CardArtTier.UR, "100%+"),
        (100, CardArtTier.UR, "100%+"),
    ],
)
def test_four_visual_card_tiers_are_deterministic(score, tier, visible):
    assert card_art_tier(score, score) is tier
    assert art_frame_for(popularity_score=score, power_score=score).visible_percent == visible


@pytest.mark.parametrize(
    ("level", "style"),
    [
        (1, "anime base"),
        (5, "anime base"),
        (6, "anime"),
        (10, "anime"),
        (11, "anime premium"),
        (20, "anime premium"),
        (21, "anime premium"),
        (25, "anime premium"),
    ],
)
def test_art_progression_is_deterministic_and_safe(level, style):
    stage = art_stage_for_level(level)
    assert stage.style == style
    assert "ropa" in stage.outfit.casefold() or "vestuario" in stage.outfit.casefold()


@pytest.mark.parametrize("level", [0, 26])
def test_art_progression_rejects_out_of_range_levels(level):
    with pytest.raises(ValueError):
        art_stage_for_level(level)


def test_visual_art_rules_cover_all_four_tiers():
    assert set(CARD_ART_RULES) == set(CardArtTier)
    assert CARD_ART_RULES[CardArtTier.R].visible_percent == "20%"
    assert CARD_ART_RULES[CardArtTier.S].visible_percent == "40%"
    assert CARD_ART_RULES[CardArtTier.SR].visible_percent == "60-80%"
    assert CARD_ART_RULES[CardArtTier.UR].visible_percent == "100%+"


def test_card_tier_outfits_remain_safe_variants():
    assert set(CARD_OUTFITS) == {CardTier.R, CardTier.SR, CardTier.UR}
    assert all("desn" not in text.casefold() for text in CARD_OUTFITS.values())
    assert all("sexual" not in text.casefold() for text in CARD_OUTFITS.values())


def test_art_prompt_spec_keeps_identity_and_unique_direction():
    prompt = art_prompt_spec(
        character_name="Anya Forger",
        anime="Spy x Family",
        level=25,
        card_tier=CardTier.UR,
        popularity_score=90,
        power_score=90,
        unique_direction="luz cálida, sonrisa traviesa, composición vertical con profundidad",
    )

    assert "Anya Forger" in prompt
    assert "Spy x Family" in prompt
    assert "Visual tier: UR" in prompt
    assert "100%+" in prompt
    assert "Unique direction:" in prompt
    assert "luz cálida" in prompt
    assert "desn" not in prompt.casefold()
    assert "sexual" not in prompt.casefold()
