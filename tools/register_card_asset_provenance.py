from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

MANIFEST = Path("assets/waifus/provenance_manifest.json")
ALLOWED_STATUSES = {"licensed", "original", "grandfathered_legacy"}
CLEARED_STATUSES = {"licensed", "original"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict:
    if not MANIFEST.is_file():
        return {"version": 1, "policy": "", "records": []}
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise SystemExit("Invalid provenance manifest: expected an object with records[]")
    return data


def register(
    asset: Path,
    *,
    status: str,
    source_url: str,
    creator: str,
    license_name: str,
    notes: str,
) -> str:
    asset = asset.resolve()
    if not asset.is_file():
        raise SystemExit(f"Asset does not exist: {asset}")

    repo_root = Path.cwd().resolve()
    try:
        relative = asset.relative_to(repo_root).as_posix()
    except ValueError as exc:
        raise SystemExit("Asset must be inside the repository") from exc

    if status not in ALLOWED_STATUSES:
        raise SystemExit(f"Unsupported status: {status}")

    if status == "licensed":
        if not license_name.strip() or not source_url.strip():
            raise SystemExit("licensed assets require --license and --source-url")
    elif status == "original":
        if not creator.strip():
            raise SystemExit("original assets require --creator")

    manifest = load_manifest()
    records = [
        record for record in manifest["records"]
        if record.get("asset") != relative
    ]
    records.append(
        {
            "asset": relative,
            "status": status,
            "rights_status": "cleared" if status in CLEARED_STATUSES else "unverified",
            "source_url": source_url.strip(),
            "creator": creator.strip() or "unknown",
            "license": license_name.strip(),
            "sha256": sha256_file(asset),
            "notes": notes.strip(),
        }
    )
    records.sort(key=lambda record: record["asset"])
    manifest["records"] = records
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return relative


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Register asset-level provenance. This tool records rights metadata and "
            "a SHA-256 hash; it does not download assets or remove watermarks."
        )
    )
    parser.add_argument("asset", type=Path, help="Existing asset inside this repository")
    parser.add_argument(
        "--status",
        choices=sorted(ALLOWED_STATUSES),
        required=True,
        help="original, licensed, or grandfathered_legacy",
    )
    parser.add_argument("--source-url", default="", help="Exact source page or repository URL")
    parser.add_argument("--creator", default="", help="Creator/rightsholder when known")
    parser.add_argument("--license", dest="license_name", default="", help="License or permission text")
    parser.add_argument("--notes", default="", help="Human-readable provenance notes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    relative = register(
        args.asset,
        status=args.status,
        source_url=args.source_url,
        creator=args.creator,
        license_name=args.license_name,
        notes=args.notes,
    )
    print(f"Registered provenance: {relative}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
