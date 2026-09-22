import pytest

import tools.waifu_drone as waifu_drone


def test_github_candidates_structure():
    """The canonical GitHub candidate helper must remain callable after migration."""
    candidates_fn = getattr(
        waifu_drone,
        "_github_candidates",
        getattr(waifu_drone, "_github_cc0_candidates", None),
    )
    assert hasattr(waifu_drone, "_github_candidates") or hasattr(
        waifu_drone, "_github_cc0_candidates"
    )
    assert callable(candidates_fn)


def test_allowed_licenses_normalization():
    """License comparisons use a normalized lowercase representation."""
    assert all(lic == lic.lower() for lic in waifu_drone.ALLOWED_LICENSES)
    allowed = {lic.lower() for lic in waifu_drone.ALLOWED_LICENSES}
    assert "cc0-1.0" in allowed


def test_quota_short_circuits_before_network(tmp_path, monkeypatch) -> None:
    quarantine = tmp_path / "quarantine"
    production = tmp_path / "production"
    quarantine.mkdir()

    for index in range(10):
        sprite = waifu_drone._make_offline_sprite(index)
        (quarantine / f"spr_{index:08x}_raw.png").write_bytes(
            sprite + b"x" * max(0, waifu_drone.MIN_PNG_BYTES - len(sprite))
        )

    monkeypatch.setattr(waifu_drone, "RAW_SPRITE_DIR", quarantine)
    monkeypatch.setattr(waifu_drone, "PROD_SPRITE_DIR", production)
    for candidate_helper in (
        "_github_candidates",
        "_oga_candidates",
        "_itch_candidates",
        "_commons_candidates",
    ):
        monkeypatch.setattr(
            waifu_drone,
            candidate_helper,
            lambda *args, _name=candidate_helper, **kwargs: pytest.fail(
                f"network candidate search should not run: {_name}"
            ),
        )

    existing = waifu_drone.get_existing_valid_sprites()
    assert len(existing) == 10
    assert waifu_drone.fetch_cc0_waifus(10) == 10


def test_generated_asset_id_is_stable() -> None:
    url = "https://example.test/sprite.png"
    assert waifu_drone.generate_asset_id(url) == waifu_drone.generate_asset_id(url)
    assert waifu_drone.generate_asset_id(url).startswith("spr_")


def test_allowed_license_set_is_strict() -> None:
    allowed = {lic.lower() for lic in waifu_drone.ALLOWED_LICENSES}
    assert "cc0-1.0" in allowed
    assert "cc-by-4.0" not in allowed
