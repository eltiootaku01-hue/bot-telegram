from __future__ import annotations

import hashlib
from pathlib import Path

CLEARED_PROVENANCE_STATUSES = {"licensed", "original"}
ALLOWED_PROVENANCE_STATUSES = CLEARED_PROVENANCE_STATUSES | {"grandfathered_legacy"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_provenance(
    path: Path,
    record: dict | None,
    *,
    failures: list[str],
) -> None:
    relative = path.as_posix()
    if record is None:
        failures.append(f"{relative}: missing asset-level provenance record")
        return

    status = record.get("status")
    if status not in ALLOWED_PROVENANCE_STATUSES:
        failures.append(f"{relative}: unsupported provenance status {status!r}")
        return

    if status in CLEARED_PROVENANCE_STATUSES:
        if record.get("rights_status") != "cleared":
            failures.append(f"{relative}: cleared asset must have rights_status=cleared")
        if status == "licensed" and (
            not str(record.get("source_url") or "").strip()
            or not str(record.get("license") or "").strip()
        ):
            failures.append(f"{relative}: licensed asset requires source_url and license")
        if status == "original" and not str(record.get("creator") or "").strip():
            failures.append(f"{relative}: original asset requires creator")
        recorded_hash = str(record.get("sha256") or "").strip().lower()
        if len(recorded_hash) != 64:
            failures.append(f"{relative}: cleared asset requires a 64-character SHA-256")
        elif recorded_hash != sha256_file(path):
            failures.append(f"{relative}: provenance SHA-256 does not match file bytes")
    else:
        if record.get("rights_status") != "unverified":
            failures.append(f"{relative}: grandfathered_legacy must remain rights_status=unverified")
