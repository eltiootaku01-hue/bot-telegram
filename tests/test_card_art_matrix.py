from app.game.card_art_matrix import (
    ART_MATRIX,
    CardArtTier,
    CardArtVariant,
    art_profile,
    build_card_art_prompt,
    production_filename,
    tier_from_label,
    validate_variant_for_tier,
)


def test_definitive_matrix_contains_all_visual_profiles() -> None:
    assert set(ART_MATRIX) == {
        CardArtTier.CLOSE_UP,
        CardArtTier.S,
        CardArtTier.SR,
        CardArtTier.UR,
    }
    assert art_profile("R").visual_phase.startswith("Fase 1")
    assert art_profile("R").framing == "primer plano / close-up"
    assert art_profile("S").visual_phase.startswith("Fase 2")
    assert art_profile("S").framing == "plano medio"
    assert art_profile("SR").visual_phase.startswith("Fase 2")
    assert art_profile("SR").framing == "plano tres cuartos"
    assert art_profile("UR").visual_phase == "Final Ascension / Magnificent Art"
    assert art_profile("UR").framing == "plano general"
    assert "cuerpo completo" in art_profile("UR").composition.lower()
    assert "efectos visuales" in art_profile("UR").composition.lower()


def test_tier_label_resolution_is_explicit() -> None:
    assert tier_from_label("d") is CardArtTier.CLOSE_UP
    assert tier_from_label("R") is CardArtTier.CLOSE_UP
    assert tier_from_label("sr") is CardArtTier.SR
    assert tier_from_label("UR") is CardArtTier.UR


def test_ur_variant_resolution_and_tier_gate() -> None:
    assert validate_variant_for_tier("UR", "holo") is CardArtVariant.UR_ALT_HOLO
    assert validate_variant_for_tier("UR", "ur-alt-holo") is CardArtVariant.UR_ALT_HOLO
    try:
        validate_variant_for_tier("SR", "ur-alt-holo")
    except ValueError as exc:
        assert "only for UR" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_production_filename_supports_ur_holo_variant() -> None:
    assert production_filename("yor-forger") == "yor-forger--normal.jpg"
    assert production_filename("yor-forger", "shiny") == "yor-forger--shiny.jpg"
    assert production_filename("yor-forger", "ur-alt-holo", tier="UR") == "yor-forger--ur-alt-holo.jpg"


def test_ur_holo_prompt_is_adult_gated_and_non_explicit() -> None:
    try:
        build_card_art_prompt(
            character_name="Adult Character",
            anime="Test",
            tier="UR",
            variant="ur-alt-holo",
            adult_eligible=False,
        )
    except ValueError as exc:
        assert "adult_eligible=true" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    prompt = build_card_art_prompt(
        character_name="Adult Character",
        anime="Test",
        tier="UR",
        variant="ur-alt-holo",
        adult_eligible=True,
    )
    assert "UR ALTERNATE HOLO/SHINY" in prompt
    assert "backlighting" in prompt.lower()
    assert "no nudity" in prompt.lower()
    assert "no sexual act" in prompt.lower()
    assert "1024x1536" in prompt


def test_non_ur_prompt_stays_non_suggestive() -> None:
    prompt = build_card_art_prompt(
        character_name="Test Character",
        anime="Test",
        tier="S",
        variant="normal",
        adult_eligible=True,
    )
    assert "NON-SUGGESTIVE PRODUCTION MODE" in prompt
    assert "no nudity" in prompt.lower()


def test_unsupported_art_tier_is_rejected() -> None:
    try:
        art_profile("A")
    except ValueError as exc:
        assert "Unsupported card art tier" in str(exc)
    else:
        raise AssertionError("expected ValueError")
