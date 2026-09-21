from app.game.cards import (
    CardVariant,
    card_for_character,
    card_variants_for,
    fusion_card_for_characters,
    generic_r_card,
)
from app.game.catalog import get_character
from app.game.models import CardTier


def test_base_character_card_tiers_are_r_s_or_sr_but_never_ur() -> None:
    for character_id in ("yor-forger", "chizuru-mizuhara", "anya"):
        card = card_for_character(get_character(character_id), seed=f"test:{character_id}")
        assert card.tier in {CardTier.R, CardTier.S, CardTier.SR}
        assert card.tier is not CardTier.UR


def test_card_variant_is_deterministic_and_includes_shiny_path() -> None:
    character = get_character("yor-forger")
    first = card_for_character(character, seed="variant-a")
    second = card_for_character(character, seed="variant-a")
    assert first == second
    assert first.variant in {CardVariant.NORMAL, CardVariant.SHINY}


def test_card_variants_produce_a_rich_preview_set() -> None:
    variants = card_variants_for(get_character("yor-forger"))
    assert len(variants) == 32
    assert len({card.card_id for card in variants}) >= 24
    assert len({card.outfit for card in variants}) > 1


def test_ur_is_only_created_by_fusion_of_two_different_base_waifus() -> None:
    first = get_character("yor-forger")
    second = get_character("nico-robin")
    card = fusion_card_for_characters(first, second, seed="fusion-1")
    assert card.tier is CardTier.UR
    assert card.is_fusion is True
    assert card.fusion_of == ("nico-robin", "yor-forger")

    try:
        fusion_card_for_characters(first, first, seed="invalid")
    except ValueError as exc:
        assert "dos" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_generic_r_cards_are_deterministic_and_not_part_of_ip_catalog() -> None:
    first = generic_r_card("generic-1")
    second = generic_r_card("generic-1")
    assert first == second
    assert first.tier is CardTier.R
    assert first.character_id.startswith("generic-r:")
    assert first.anime == "Ciudad Animals — original"
