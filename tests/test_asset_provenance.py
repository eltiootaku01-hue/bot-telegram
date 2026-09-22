import hashlib
from pathlib import Path

from app.game.art_provenance import validate_provenance


def test_cleared_provenance_accepts_matching_sha256(tmp_path: Path) -> None:
    asset = tmp_path / "card.jpg"
    asset.write_bytes(b"approved-art")
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    failures: list[str] = []

    validate_provenance(
        asset,
        {
            "asset": str(asset).replace("\\", "/"),
            "status": "licensed",
            "rights_status": "cleared",
            "source_url": "https://example.invalid/license",
            "creator": "Artist",
            "license": "CC BY 4.0",
            "sha256": digest,
        },
        root=tmp_path / "production" / "cards",
        failures=failures,
    )

    assert failures == []


def test_cleared_provenance_rejects_changed_file_bytes(tmp_path: Path) -> None:
    asset = tmp_path / "card.jpg"
    asset.write_bytes(b"approved-art")
    failures: list[str] = []

    validate_provenance(
        asset,
        {
            "asset": str(asset).replace("\\", "/"),
            "status": "original",
            "rights_status": "cleared",
            "source_url": "",
            "creator": "Project Artist",
            "license": "Original",
            "sha256": "0" * 64,
        },
        root=tmp_path / "production" / "cards",
        failures=failures,
    )

    assert any("SHA-256" in failure for failure in failures)


def test_grandfathered_legacy_is_explicitly_unverified(tmp_path: Path, capsys) -> None:
    asset = tmp_path / "card.jpg"
    asset.write_bytes(b"legacy")
    failures: list[str] = []

    validate_provenance(
        asset,
        {
            "asset": str(asset).replace("\\", "/"),
            "status": "grandfathered_legacy",
            "rights_status": "unverified",
        },
        root=tmp_path / "production" / "cards",
        failures=failures,
    )

    assert failures == []
    assert "grandfathered legacy" in capsys.readouterr().err


def test_missing_provenance_record_is_a_hard_failure(tmp_path: Path) -> None:
    asset = tmp_path / "card.jpg"
    asset.write_bytes(b"new-art")
    failures: list[str] = []

    validate_provenance(
        asset,
        None,
        root=tmp_path / "production" / "cards",
        failures=failures,
    )

    assert any("missing asset-level provenance" in failure for failure in failures)
