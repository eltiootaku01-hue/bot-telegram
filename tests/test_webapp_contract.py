from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBAPP = ROOT / "webapp"


def test_combat_frontend_imports_lightweight_effects_module() -> None:
    combat = (WEBAPP / "js" / "combat.js").read_text(encoding="utf-8")
    effects = (WEBAPP / "js" / "effects.js").read_text(encoding="utf-8")

    assert './effects.js' in combat
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
