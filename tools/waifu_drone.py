from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

RAW_SPRITE_DIR = Path("assets/raw/sprites/quarantine")
PROD_SPRITE_DIR = Path("assets/production/sprites")
MANIFEST_FILE = RAW_SPRITE_DIR / "manifest.json"

SEARCH_TAGS = (
    "anime character sprite CC0",
    "rpg sprite CC0",
    "pixel character CC0",
    "game character sprite CC0",
)
ALLOWED_LICENSES = {"CC0-1.0", "CC0", "Public domain", "Public Domain"}
BLOCKED_TERMS = {
    "nsfw", "porn", "hentai", "explicit", "nude", "nudity",
    "erotic", "fetish", "watermark", "logo", "preview",
}
API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "WaifuMon-WaifuDrone/1.0"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def generate_asset_id(url: str) -> str:
    return "spr_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]


def _plain(value: object) -> str:
    return re.sub(r"<[^>]+>", " ", str(value or ""))


def _metadata_text(page: dict, info: dict) -> str:
    ext = info.get("extmetadata") or {}
    values = [
        page.get("title", ""),
        ext.get("ImageDescription", {}),
        ext.get("Categories", {}),
    ]
    return " ".join(_plain(v.get("value", "") if isinstance(v, dict) else v) for v in values).casefold()


def _license(page: dict) -> str:
    ext = page.get("_imageinfo", {}).get("extmetadata", {}) if page.get("_imageinfo") else {}
    return str(
        next(
            (
                value.get("value", "") if isinstance(value, dict) else value
                for key in ("LicenseShortName", "UsageTerms", "License")
                if (value := ext.get(key))
                and str(value.get("value", "") if isinstance(value, dict) else value).strip()
                in ALLOWED_LICENSES
            ),
            "",
        )
    ).strip()


def _api_get(params: dict[str, str]) -> dict:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def search_candidates() -> list[dict]:
    seen: set[str] = set()
    candidates: list[dict] = []

    for tag in SEARCH_TAGS:
        data = _api_get(
            {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "generator": "search",
                "gsrnamespace": "6",
                "gsrsearch": tag,
                "gsrlimit": "50",
                "prop": "imageinfo",
                "iiprop": "url|mime|size|extmetadata",
            }
        )
        for page in data.get("query", {}).get("pages", []):
            imageinfo = page.get("imageinfo") or []
            if not imageinfo:
                continue
            info = imageinfo[0]
            url = str(info.get("url", "")).strip()
            mime = str(info.get("mime", "")).lower()
            page["_imageinfo"] = info

            if not url or url in seen:
                continue
            seen.add(url)
            if mime != "image/png" or not urllib.parse.urlparse(url).path.lower().endswith(".png"):
                continue

            license_name = _license(page)
            if license_name not in ALLOWED_LICENSES:
                continue

            if any(term in _metadata_text(page, info) for term in BLOCKED_TERMS):
                continue

            candidates.append(
                {
                    "title": str(page.get("title", "")),
                    "source_page": "https://commons.wikimedia.org/wiki/"
                    + str(page.get("title", "")).replace(" ", "_"),
                    "source_url": url,
                    "license": license_name,
                    "mime": mime,
                    "size": int(info.get("size") or 0),
                }
            )
    return candidates


def _valid_png(data: bytes) -> bool:
    return len(data) >= 33 and data.startswith(PNG_SIGNATURE) and data[12:16] == b"IHDR"


def fetch_cc0_waifus(target_amount: int = 10) -> int:
    if target_amount < 1:
        raise ValueError("target_amount must be positive")

    RAW_SPRITE_DIR.mkdir(parents=True, exist_ok=True)
    PROD_SPRITE_DIR.mkdir(parents=True, exist_ok=True)

    candidates = search_candidates()
    downloaded = 0
    records = []

    for item in candidates:
        if downloaded >= target_amount:
            break

        asset_id = generate_asset_id(item["source_url"])
        destination = RAW_SPRITE_DIR / f"{asset_id}_raw.png"
        if destination.exists():
            continue

        request = urllib.request.Request(
            item["source_url"],
            headers={"User-Agent": USER_AGENT, "Accept": "image/png"},
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read()
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            if content_type not in {"image/png", "application/octet-stream"}:
                continue
            if not _valid_png(data):
                continue

            destination.write_bytes(data)
            records.append(
                {
                    "asset_id": asset_id,
                    "file": destination.as_posix(),
                    "source_page": item["source_page"],
                    "source_url": item["source_url"],
                    "license": item["license"],
                    "mime": "image/png",
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "status": "quarantine_only",
                }
            )
            downloaded += 1
            print(f"[OK] {destination}")
            time.sleep(1.5)
        except Exception as exc:
            print(f"[SKIP] {item['source_url']}: {exc}")

    MANIFEST_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"=== {downloaded}/{target_amount} NUEVOS ASSETS ===")
    return downloaded


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-amount", type=int, default=10)
    args = parser.parse_args()
    raise SystemExit(0 if fetch_cc0_waifus(args.target_amount) >= args.target_amount else 1)
