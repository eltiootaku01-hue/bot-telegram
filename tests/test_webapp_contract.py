from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBAPP = ROOT / "webapp"


def test_combat_frontend_imports_lightweight_effects_module() -> None:
    combat = (WEBAPP / "js" / "combat.js").read_text(encoding="utf-8")
    effects = (WEBAPP / "js" / "effects.js").read_text(encoding="utf-8")

    assert './effects.js' in combat
    assert '../assets/production/sprites/' in combat
    assert '../assets/production/cards/' in combat
    assert "LightweightCombatEffects" in effects
    assert "MAX_PARTICLES = 96" in effects


def test_combat_frontend_keeps_backend_as_authority() -> None:
    combat = (WEBAPP / "js" / "main.js").read_text(encoding="utf-8")
    canvas = (WEBAPP / "js" / "combat.js").read_text(encoding="utf-8")

    assert "/api/combat/action" in (WEBAPP / "js" / "api.js").read_text(encoding="utf-8")
    assert "result.damage" in combat
    assert "defender_hp" in combat
    assert "authority real" not in canvas.casefold()


def test_magenta_processor_is_present_and_isolated_from_runtime() -> None:
    processor = ROOT / "tools" / "prepare_magenta_png.py"
    source = processor.read_text(encoding="utf-8")

    assert "MAGENTA = (255, 0, 255)" in source
    assert "alpha" in source
    assert "assets/production" not in source or "destination" in source


def test_holographic_tcg_card_contract_is_present() -> None:
    index = (WEBAPP / "index.html").read_text(encoding="utf-8")
    main = (WEBAPP / "js" / "main.js").read_text(encoding="utf-8")
    style = (WEBAPP / "css" / "style.css").read_text(encoding="utf-8")

    assert 'class="tcg-card" id="sujetoCero"' in index
    assert 'class="foil-glare" id="hologram"' in index
    assert 'id="tcg-card-art"' in index
    assert "setupHolographicCard" in main
    assert "deviceorientation" in main
    assert "requestPermission" in main
    assert ".tcg-card" in style
    assert ".foil-glare" in style
    assert "color-dodge" in style
    assert "--card-tilt-x" in style
    assert "--glare-x" in style


def test_card_admin_form_and_client_contract_are_present() -> None:
    index = (WEBAPP / "index.html").read_text(encoding="utf-8")
    api = (WEBAPP / "js" / "api.js").read_text(encoding="utf-8")
    main = (WEBAPP / "js" / "main.js").read_text(encoding="utf-8")

    assert 'id="deck-builder-tab"' in index
    assert 'id="create-card-form"' in index
    assert 'id="card-image"' in index
    assert 'name="character-name"' in index
    assert 'name="anime-origin"' in index
    assert 'name="rarity"' in index
    assert 'name="source-provider"' in index
    assert 'name="collection-points"' in index
    assert "createCard(formData)" in api
    assert "/api/admin/cards" in api
    assert "setupCardAdmin" in main
    assert "Ya forma parte del pool de /roll" in main
