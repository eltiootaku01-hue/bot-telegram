from app.modules.cami_media.publisher import CamiMediaPublisher


def test_cami_publisher_builds_a_safe_caption() -> None:
    class Asset:
        character_id = "asuna-kirigaya"
        anime = "Sword & Art"
        tags = "waifu, conejita"

    caption = CamiMediaPublisher._caption(Asset())
    assert "asuna kirigaya" in caption
    assert "Sword &amp; Art" in caption
    assert "#waifu" in caption
    assert "#conejita" in caption
