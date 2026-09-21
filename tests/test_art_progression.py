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
    ("tier", "visible"),
    [
        (CardArtTier.R, "20%"),
        (CardArtTier.S, "40%"),
        (CardArtTier.SR, "60-80%"),
        (CardArtTier.UR, "100%+"),
    ],
)
def test_four_visual_card_tiers_are_deterministic(tier, visible):
    assert card_art_tier(CardTier(tier.value)) is tier
    assert art_frame_for(card_tier=CardTier(tier.value)).visible_percent == visible




@pytest.mark.parametrize(
    ("level", "style"),
    [
        (1, "chibi"),
        (5, "chibi"),
        (6, "anime"),
        (10, "anime"),
        (11, "anime premium"),
        (20, "anime premium"),
        (21, "anime premium"),
        (25, "anime premium"),
        (30, "anime premium"),
    ],
)
def test_art_progression_is_deterministic_and_safe(level, style):
    stage = art_stage_for_level(level)
    assert stage.style == style
    assert "ropa" in stage.outfit.casefold() or "vestuario" in stage.outfit.casefold()


@pytest.mark.parametrize("level", [0, 31])
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
    assert set(CARD_OUTFITS) == {CardTier.R, CardTier.S, CardTier.SR, CardTier.UR}
    assert all("desn" not in text.casefold() for text in CARD_OUTFITS.values())
    assert all("sexual" not in text.casefold() for text in CARD_OUTFITS.values())


def test_art_prompt_spec_keeps_identity_and_unique_direction():
    prompt = art_prompt_spec(
        character_name="Anya Forger",
        anime="Spy x Family",
        level=25,
        card_tier=CardTier.SR,
        variant="shiny",
        popularity_score=90,
        power_score=90,
        unique_direction="luz cálida, sonrisa traviesa, composición vertical con profundidad",
    )

    assert "Anya Forger" in prompt
    assert "Spy x Family" in prompt
    assert "Visual tier: SR" in prompt
    assert "60-80%" in prompt
    assert "Unique direction:" in prompt
    assert "luz cálida" in prompt
    assert "desn" not in prompt.casefold()
    assert "sexual" not in prompt.casefold()


def test_art_prompt_prefers_explicit_character_id_for_visual_direction() -> None:
    from app.game.models import CardTier

    prompt = art_prompt_spec(
        character_name="Alisa Mikhailovna Kujo",
        anime="Alya Sometimes Hides Her Feelings in Russian",
        character_id="alisa-kujo",
        level=25,
        card_tier=CardTier.SR,
        popularity_score=100,
        power_score=42,
    )

    assert "azul hielo" in prompt
    assert "cafetería escolar" in prompt
    assert "Character: Alisa Mikhailovna Kujo" in prompt


def test_waifumon_rarity_art_has_separate_combat_class_visibility() -> None:
    from app.game.art_progression import (
        WAIFUMON_RARITY_ART_VISIBILITY,
        waifumon_rarity_art_visibility,
    )
    from app.game.models import Rarity

    assert set(WAIFUMON_RARITY_ART_VISIBILITY) == set(Rarity)
    assert waifumon_rarity_art_visibility(Rarity.D) == "15%"
    assert waifumon_rarity_art_visibility(Rarity.SSS) == "100%"
