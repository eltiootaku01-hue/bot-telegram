import pytest

from app.game.art_progression import CARD_OUTFITS, art_prompt_spec, art_stage_for_level
from app.game.models import CardTier


@pytest.mark.parametrize(
    ("level", "style", "framing"),
    [
        (1, "chibi", "retrato de cabeza y hombros"),
        (5, "chibi", "retrato de cabeza y hombros"),
        (6, "anime", "medio cuerpo"),
        (10, "anime", "medio cuerpo"),
        (11, "anime", "cuerpo completo"),
        (15, "anime", "cuerpo completo"),
        (16, "anime premium", "cuerpo completo con efectos"),
        (20, "anime premium", "cuerpo completo con efectos"),
        (21, "anime premium", "ilustración completa"),
        (25, "anime premium", "ilustración completa"),
    ],
)
def test_art_progression_is_deterministic_and_non_explicit(level, style, framing):
    stage = art_stage_for_level(level)

    assert stage.style == style
    assert stage.framing == framing
    assert "ropa" in stage.outfit.casefold() or "vestuario" in stage.outfit.casefold()


@pytest.mark.parametrize("level", [0, 26])
def test_art_progression_rejects_out_of_range_levels(level):
    with pytest.raises(ValueError):
        art_stage_for_level(level)


def test_card_tier_outfits_are_safe_variants():
    assert set(CARD_OUTFITS) == {CardTier.R, CardTier.SR, CardTier.UR}
    assert all("desn" not in text.casefold() for text in CARD_OUTFITS.values())
    assert all("sexual" not in text.casefold() for text in CARD_OUTFITS.values())


def test_art_prompt_spec_keeps_same_character_identity_across_tiers():
    base = art_prompt_spec(
        character_name="Anya Forger",
        anime="Spy x Family",
        level=25,
        card_tier=CardTier.R,
    )
    ultra = art_prompt_spec(
        character_name="Anya Forger",
        anime="Spy x Family",
        level=25,
        card_tier=CardTier.UR,
    )

    assert "Anya Forger" in base and "Anya Forger" in ultra
    assert "Spy x Family" in base and "Spy x Family" in ultra
    assert "version ultra" in ultra.casefold()
    assert "desn" not in ultra.casefold()
