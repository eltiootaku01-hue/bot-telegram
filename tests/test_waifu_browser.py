from app.game.waifu_browser import PAGE_SIZE, page_for, render_page


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
