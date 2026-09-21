from app.game.catalog import CHARACTERS, catalog_size, get_character
from app.game.models import CardTier, Element, Rarity, card_tier_from_scores, rarity_from_power
from app.game.waifu_catalog import ALL_WAIFUS, ANIME_CORNER_2025_SOURCE, RANKER_2026_SOURCE


def test_catalog_contains_source_backed_waifus() -> None:
    assert catalog_size() == len(ALL_WAIFUS) + 1
    assert "anya" in CHARACTERS
    assert "yor-forger" in CHARACTERS
    assert "maomao" in CHARACTERS
    assert "taiga" in CHARACTERS


def test_two_axes_and_card_tier_are_independent() -> None:
    yor = get_character("yor-forger")
    maomao = get_character("maomao")

    assert yor.popularity_rank == 2
    assert yor.power_score == 86
    assert yor.rarity is Rarity.SS
    assert yor.card_tier is CardTier.UR
    assert yor.element is Element.DARK

    assert maomao.popularity_rank == 1
    assert maomao.power_score == 45
    assert maomao.rarity is Rarity.B
    assert maomao.card_tier is CardTier.SR
    assert maomao.element is Element.MIND


def test_all_source_backed_entries_have_valid_game_axes() -> None:
    for definition in ALL_WAIFUS:
        character = get_character("anya" if definition.id == "anya-forger" else definition.id)
        assert character.power_score == definition.power_score
        assert character.popularity_score == definition.popularity_score
        assert character.element is definition.element
        assert character.rarity is rarity_from_power(definition.power_score)
        assert character.popularity_source in {
            RANKER_2026_SOURCE,
            ANIME_CORNER_2025_SOURCE,
        }
        assert character.card_tier is card_tier_from_scores(
            character.popularity_score,
            character.power_score,
        )


def test_ranked_catalog_has_unique_ids_and_rankings() -> None:
    assert len({item.id for item in ALL_WAIFUS}) == len(ALL_WAIFUS)
    assert all(
        item.ranker_rank is not None or item.recent_rank is not None
        for item in ALL_WAIFUS
    )


def test_card_tier_boundaries_are_stable() -> None:
    assert card_tier_from_scores(39, 39) is CardTier.R
    assert card_tier_from_scores(40, 40) is CardTier.S
    assert card_tier_from_scores(51, 51) is CardTier.S
    assert card_tier_from_scores(52, 52) is CardTier.SR
    assert card_tier_from_scores(77, 77) is CardTier.SR
    assert card_tier_from_scores(78, 78) is CardTier.UR
    assert card_tier_from_scores(80, 80) is CardTier.UR
