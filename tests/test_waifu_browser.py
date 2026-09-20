from app.game.models import Element
from app.game.waifu_browser import (
    PAGE_SIZE,
    WaifuFilter,
    WaifuFilterField,
    page_for,
    render_detail,
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


def test_waifu_catalog_filter_keyboard_uses_compact_telegram_callbacks() -> None:
    from app.ui.game_keyboards import (
        waifu_catalog_keyboard,
        waifu_filter_categories_keyboard,
        waifu_filter_options_keyboard,
    )

    active_filter = WaifuFilter(WaifuFilterField.SOURCE, "recent")
    catalog = waifu_catalog_keyboard(2, 3, active_filter)
    callbacks = [
        button.callback_data
        for row in catalog.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert "game:waifus:page:3:s:recent" in callbacks
    assert "game:waifus:filters" in callbacks
    assert "game:waifus:clear" in callbacks

    categories = waifu_filter_categories_keyboard()
    category_callbacks = [
        button.callback_data
        for row in categories.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert {
        "game:waifus:filter:e",
        "game:waifus:filter:c",
        "game:waifus:filter:r",
        "game:waifus:filter:s",
    } <= set(category_callbacks)

    source_options = waifu_filter_options_keyboard("s")
    source_callbacks = [
        button.callback_data
        for row in source_options.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert "game:waifus:set:s:ranker" in source_callbacks
    assert "game:waifus:set:s:recent" in source_callbacks
    assert "game:waifus:set:s:local" in source_callbacks


def test_waifu_detail_render_is_local_and_explicit_about_provenance() -> None:
    from app.game.catalog import get_character

    character = get_character("yor-forger")
    rendered = render_detail(character)

    assert "Yor Forger" in rendered
    assert "SPY x FAMILY" in rendered
    assert "Carta:" in rendered
    assert "Clase:" in rendered
    assert "Elemento:" in rendered
    assert "Poder de balance:" in rendered
    assert "Popularidad normalizada:" in rendered
    assert "Ranker · snapshot 2026-07-15" in rendered
    assert "no es un porcentaje universal" in rendered
