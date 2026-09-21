from app.game.card_art_matrix import (
    ART_MATRIX,
    CardArtTier,
    art_profile,
    build_card_art_prompt,
    production_filename,
    tier_from_label,
)


def test_definitive_matrix_contains_all_visual_profiles() -> None:
    assert set(ART_MATRIX) == {
        CardArtTier.CLOSE_UP,
        CardArtTier.S,
        CardArtTier.SR,
        CardArtTier.UR,
    }
    assert art_profile("D").tier is CardArtTier.CLOSE_UP
    assert art_profile("C").tier is CardArtTier.CLOSE_UP
    assert art_profile("B").tier is CardArtTier.CLOSE_UP
    assert art_profile("R").tier is CardArtTier.CLOSE_UP
    assert art_profile("S").framing == "plano medio"
    assert art_profile("SR").framing == "plano tres cuartos"
    assert art_profile("UR").framing == "plano general"


def test_tier_label_resolution_is_explicit() -> None:
    assert tier_from_label("d") is CardArtTier.CLOSE_UP
    assert tier_from_label("R") is CardArtTier.CLOSE_UP
    assert tier_from_label("sr") is CardArtTier.SR
    assert tier_from_label("UR") is CardArtTier.UR


def test_production_filename_is_canonical_jpg() -> None:
    assert production_filename("yor-forger") == "yor-forger--normal.jpg"
    assert production_filename("yor-forger", "shiny") == "yor-forger--shiny.jpg"


def test_suggestive_tiers_are_gated_by_explicit_adult_eligibility() -> None:
    guarded = build_card_art_prompt(
        character_name="Test Character",
        anime="Test",
        tier="UR",
        adult_eligible=False,
    )
    assert "NON-SUGGESTIVE PRODUCTION MODE" in guarded
    assert "no nudity" in guarded.lower()
    assert "sexualized minors" in guarded.lower()
    assert "lencería" not in guarded.lower()
    assert "vestuario tematico completamente cubierto" in guarded.lower()

    adult = build_card_art_prompt(
        character_name="Adult Character",
        anime="Test",
        tier="UR",
        adult_eligible=True,
    )
    assert "ADULT-ELIGIBLE NON-EXPLICIT MODE" in adult
    assert "no nudity" in adult.lower()


def test_ur_prompt_contains_strict_full_body_quality_checks() -> None:
    prompt = build_card_art_prompt(
        character_name="Test Character",
        anime="Test",
        tier="UR",
        adult_eligible=True,
    )
    assert "cuerpo completo" in prompt.lower()
    assert "hands" in prompt.lower()
    assert "perspective" in prompt.lower()
    assert "1024x1536" in prompt


def test_unsupported_art_tier_is_rejected() -> None:
    try:
        art_profile("A")
    except ValueError as exc:
        assert "Unsupported card art tier" in str(exc)
    else:
        raise AssertionError("expected ValueError")
