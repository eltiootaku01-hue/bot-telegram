from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
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
OGA_PAGES = (
    "https://opengameart.org/content/simple-character-sprite",
    "https://opengameart.org/content/hero-character-sprite-sheet",
    "https://opengameart.org/content/character-sprite-walk-animation",
    "https://opengameart.org/content/rpg-character-sprites",
    "https://opengameart.org/content/character-3",
    "https://opengameart.org/content/character-images",
    "https://opengameart.org/content/simple-character-1",
    "https://opengameart.org/content/hero-character",
    "https://opengameart.org/content/pixel-character",
    "https://opengameart.org/content/8-bit-character",
    "https://opengameart.org/content/bird-like-rpg-character",
)
USER_AGENT = "WaifuMon-WaifuDrone/1.3"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def generate_asset_id(url: str) -> str:
    return "spr_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]


def _plain(value: object) -> str:
    return re.sub(r"<[^>]+>", " ", str(value or ""))


def _license(page: dict) -> str:
    ext = ((page.get("imageinfo") or [{}])[0]).get("extmetadata") or {}
    for key in ("LicenseShortName", "UsageTerms", "License"):
        value = ext.get(key)
        if isinstance(value, dict):
            value = value.get("value", "")
        value = str(value or "").strip()
        if value in ALLOWED_LICENSES:
            return value
    return ""


def _blocked(page: dict) -> bool:
    info = (page.get("imageinfo") or [{}])[0]
    ext = info.get("extmetadata") or {}
    haystack = " ".join(
        [
            _plain(page.get("title")),
            _plain(ext.get("ImageDescription", {})),
            _plain(ext.get("Categories", {})),
        ]
    ).casefold()
    return any(term in haystack for term in BLOCKED_TERMS)


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", "replace")


def _oga_candidates() -> list[dict]:
    candidates = []
    seen = set()

    for page_url in OGA_PAGES:
        try:
            html = _fetch_text(page_url)
        except Exception as exc:
            print("[OGA] " + page_url + ": " + str(exc))
            continue

        lowered = re.sub(r"\\s+", " ", html).casefold()
        if "cc0" not in lowered:
            continue
        if any(term in lowered for term in BLOCKED_TERMS):
            continue

        links = re.findall(r'href=["\']([^"\']+\.png(?:\?[^"\']*)?)["\']', html, re.IGNORECASE)
        for link in links:
            url = urllib.parse.urljoin(page_url, link)
            parsed = urllib.parse.urlparse(url)
            if parsed.netloc != "opengameart.org":
                continue
            if "/modules/file/icons/" in parsed.path:
                continue
            if not parsed.path.casefold().endswith(".png"):
                continue
            if url in seen:
                continue
            seen.add(url)
            title = Path(parsed.path).name
            candidates.append(
                {
                    "title": title,
                    "source_page": page_url,
                    "source_url": url,
                    "license": "CC0",
                }
            )
    return candidates


def _api_get(params: dict[str, str]) -> dict:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        API_URL + "?" + query,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def search_candidates(target_amount: int) -> list[dict]:
    candidates = []
    seen = set()

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
                "iiurlwidth": "256",
            }
        )
        for page in data.get("query", {}).get("pages", []):
            info_list = page.get("imageinfo") or []
            if not info_list:
                continue
            info = info_list[0]
            url = str(info.get("thumburl") or info.get("url") or "").strip()
            mime = str(info.get("thumbmime") or info.get("mime") or "").casefold()
            if not url or url in seen:
                continue
            seen.add(url)
            if mime != "image/png":
                continue
            if not urllib.parse.urlparse(url).path.casefold().endswith(".png"):
                continue
            if _license(page) not in ALLOWED_LICENSES:
                continue
            if _blocked(page):
                continue

            title = str(page.get("title", "")).strip()
            candidates.append(
                {
                    "title": title,
                    "source_page": "https://commons.wikimedia.org/wiki/"
                    + urllib.parse.quote(title.replace(" ", "_"), safe=":/()_,.-"),
                    "source_url": url,
                    "license": _license(page),
                }
            )
            if len(candidates) >= target_amount * 3:
                return candidates

    return candidates


def _valid_png(data: bytes) -> bool:
    return (
        len(data) >= 33
        and data.startswith(PNG_SIGNATURE)
        and data[12:16] == b"IHDR"
    )


def _download_png(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "image/png"},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read()
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].casefold()
                if content_type not in {"image/png", "application/octet-stream"}:
                    raise ValueError("unexpected content type: " + repr(content_type))
                if not _valid_png(data):
                    raise ValueError("download is not a valid PNG")
                return data
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 3:
                raise
            retry_after = exc.headers.get("Retry-After", "")
            try:
                delay = max(3.0, float(retry_after))
            except ValueError:
                delay = 3.0 * (2**attempt)
            print(f"[RADAR] Wikimedia rate limit; retrying in {delay:.1f}s")
            time.sleep(delay)
    raise RuntimeError("unreachable download state")


def fetch_cc0_waifus(target_amount: int = 10) -> int:
    if target_amount < 1:
        raise ValueError("target_amount must be positive")

    RAW_SPRITE_DIR.mkdir(parents=True, exist_ok=True)
    PROD_SPRITE_DIR.mkdir(parents=True, exist_ok=True)

    candidates = _oga_candidates()
    if len(candidates) < target_amount:
        print("[RADAR] OpenGameArt no aportó suficientes candidatos; usando Wikimedia Commons como respaldo.")
        candidates.extend(search_candidates(target_amount))
    downloaded = 0
    records = []

    for item in candidates:
        if downloaded >= target_amount:
            break

        asset_id = generate_asset_id(item["source_url"])
        destination = RAW_SPRITE_DIR / f"{asset_id}_raw.png"
        if destination.exists():
            continue

        print("[INTERCEPTANDO] " + item["title"])
        try:
            data = _download_png(item["source_url"])
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
            print("[OK] " + destination.as_posix())
            time.sleep(2.5)
        except Exception as exc:
            print("[SKIP] " + item["source_url"] + ": " + str(exc))
            destination.unlink(missing_ok=True)

    MANIFEST_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    total = sum(1 for path in RAW_SPRITE_DIR.glob("*.png") if path.is_file())
    print(f"=== {downloaded}/{target_amount} NUEVOS; {total} PNG EN CUARENTENA ===")
    return downloaded


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WaifuMon CC0/public-domain sprite drone")
    parser.add_argument("--target-amount", type=int, default=10)
    args = parser.parse_args()
    raise SystemExit(0 if fetch_cc0_waifus(args.target_amount) >= args.target_amount else 1)
