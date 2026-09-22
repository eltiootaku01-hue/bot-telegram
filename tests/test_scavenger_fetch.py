import json
import zipfile
from pathlib import Path

import pytest

from tools.scavenger_fetch import ScavengerError, _extract_zip, _safe_member_path, load_manifest


def test_safe_member_path_rejects_traversal(tmp_path: Path) -> None:
    target = tmp_path / "raw"
    target.mkdir()

    with pytest.raises(ScavengerError):
        _safe_member_path(target, "../outside.txt")

    with pytest.raises(ScavengerError):
        _safe_member_path(target, "/absolute/file.txt")


def test_extract_zip_rejects_traversal(tmp_path: Path) -> None:
    target = tmp_path / "raw"
    target.mkdir()
    archive_path = tmp_path / "malicious.zip"

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../outside.txt", b"blocked")

    with pytest.raises(ScavengerError):
        _extract_zip(archive_path, target)

    assert not (tmp_path / "outside.txt").exists()


def test_extract_zip_accepts_normal_members(tmp_path: Path) -> None:
    target = tmp_path / "raw"
    target.mkdir()
    archive_path = tmp_path / "safe.zip"

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("effects/hit.png", b"test")

    assert _extract_zip(archive_path, target) == 1
    assert (target / "effects" / "hit.png").read_bytes() == b"test"


def test_manifest_contains_only_license_verified_automatic_downloads() -> None:
    path = Path("scavenger_manifest.json")
    data = load_manifest(path)

    assert data["version"] == "1.4.0"
    assert data["downloads"]
    assert all(item["license_verified"] is True for item in data["downloads"])
    assert all(item["url"].startswith(("https://", "http://")) for item in data["downloads"])

    for item in data["research_only"]:
        assert item["status"] != "approved_for_automatic_download"


def test_manifest_is_valid_json() -> None:
    data = json.loads(Path("scavenger_manifest.json").read_text(encoding="utf-8"))
    assert data["project"] == "WaifuMon Scavenger Protocol"
