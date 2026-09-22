from pathlib import Path

import pytest

import tools.waifu_drone as drone


def test_quota_short_circuits_before_network(tmp_path, monkeypatch) -> None:
    quarantine = tmp_path / "quarantine"
    production = tmp_path / "production"
    quarantine.mkdir()

    for index in range(10):
        (quarantine / f"spr_{index:08x}_raw.png").write_bytes(
            drone.PNG_SIGNATURE + b"x" * 1024
        )

    monkeypatch.setattr(drone, "RAW_SPRITE_DIR", quarantine)
    monkeypatch.setattr(drone, "PROD_SPRITE_DIR", production)
    monkeypatch.setattr(
        drone,
        "_github_cc0_candidates",
        lambda: pytest.fail("network candidate search should not run"),
    )

    assert drone.fetch_cc0_waifus(10) == 10


def test_generated_asset_id_is_stable() -> None:
    url = "https://example.test/sprite.png"
    assert drone.generate_asset_id(url) == drone.generate_asset_id(url)
    assert drone.generate_asset_id(url).startswith("spr_")


def test_allowed_license_set_is_strict() -> None:
    assert "CC0-1.0" in drone.ALLOWED_LICENSES
    assert "MIT" not in drone.ALLOWED_LICENSES
    assert "CC-BY-4.0" not in drone.ALLOWED_LICENSES
