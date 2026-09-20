from app.game.models import Element
from app.game.waifu_browser import (
    PAGE_SIZE,
    WaifuFilter,
    WaifuFilterField,
    page_for,
    render_page,
)


def test_waifu_browser_paginates_full_catalog_deterministically() -> None:
    first = page_for(1)
    last = page_for(first.total_pages)

    assert first.page == 1
    assert first.characters
    assert len(first.characters) <= PAGE_SIZE
    assert last.page == first.total_pages
    assert last.characters
    assert first.characters[0].popularity_rank == 1
    assert "Catálogo de waifus" in render_page(first)


def test_waifu_browser_clamps_out_of_range_pages() -> None:
    first = page_for(0)
    last = page_for(9999)

    assert first.page == 1
    assert last.page == last.total_pages


def test_waifu_browser_filters_by_element_card_rarity_and_source() -> None:
    element = page_for(
        1,
        active_filter=WaifuFilter(WaifuFilterField.ELEMENT, Element.ICE.value),
    )
    assert element.characters
    assert all(character.element is Element.ICE for character in element.characters)

    card = page_for(
        1,
        active_filter=WaifuFilter(WaifuFilterField.CARD, "ur"),
    )
    assert card.characters
    assert all(character.card_tier.value == "UR" for character in card.characters)

    rarity = page_for(
        1,
        active_filter=WaifuFilter(WaifuFilterField.RARITY, "sss"),
    )
    assert rarity.characters
    assert all(character.rarity.value == "SSS" for character in rarity.characters)

    source = page_for(
        1,
        active_filter=WaifuFilter(WaifuFilterField.SOURCE, "recent"),
    )
    assert source.characters
    assert all("Anime Corner" in character.popularity_source for character in source.characters)


def test_waifu_browser_local_source_keeps_taiga_discoverable() -> None:
    page = page_for(
        1,
        active_filter=WaifuFilter(WaifuFilterField.SOURCE, "local"),
    )
    assert any(character.id == "taiga" for character in page.characters)


def test_waifu_browser_preserves_filter_across_pages() -> None:
    active_filter = WaifuFilter(WaifuFilterField.ELEMENT, Element.DARK.value)
    first = page_for(1, active_filter=active_filter)
    second = page_for(2, active_filter=active_filter)

    assert first.active_filter == active_filter
    assert second.active_filter == active_filter
    assert all(character.element is Element.DARK for character in second.characters)


def test_waifu_filter_parser_rejects_unknown_fields() -> None:
    assert WaifuFilter.from_code("x", "anything") is None
