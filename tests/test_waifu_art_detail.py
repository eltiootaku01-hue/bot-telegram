from app.game.art_progression import art_frame_for
from app.game.catalog import get_character
from app.game.waifu_browser import render_detail


def test_waifu_detail_exposes_visual_art_tier() -> None:
    character = get_character("yor-forger")
    rendered = render_detail(character)
    frame = art_frame_for(
        popularity_score=character.popularity_score,
        power_score=character.power_score,
    )

    assert "Arte:" in rendered
    assert frame.tier.value in rendered
    assert frame.visible_percent in rendered
