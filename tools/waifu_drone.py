from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path


RAW_SPRITE_DIR = Path("assets/raw/sprites/quarantine")
PROD_SPRITE_DIR = Path("assets/production/sprites")
MANIFEST_FILE = RAW_SPRITE_DIR / "manifest.json"
REJECTED_MANIFEST_FILE = RAW_SPRITE_DIR / "rejected_manifest.json"

SEARCH_TAGS = (
    "anime character sprite cc0",
    "rpg sprite cc0",
    "pixel character cc0",
    "game character sprite cc0",
    "anime character public domain",
    "rpg sprite public domain",
)

ALLOWED_LICENSES = {
    "cc0",
    "cc0-1.0",
    "creative commons zero",
    "creative commons zero 1.0",
    "public domain",
    "public domain dedication",
    "mit",
    "mit license",
}

BLOCKED_TERMS = {
    "nsfw",
    "porn",
    "hentai",
    "explicit",
    "nude",
    "nudity",
    "erotic",
    "fetish",
    "watermark",
    "watermarked",
    "logo",
    "preview image",
    "character set",
    "charset",
    "unicode",
    "hexadecimal",
    "typeface",
    "font",
    "icon",
    "lamp",
    "lantern",
    "item",
    "object",
    "weapon icon",
}

REQUIRED_TERMS = {
    "sprite",
    "character",
    "player",
    "npc",
    "hero",
    "ranger",
    "wizard",
    "knight",
    "archer",
    "rogue",
    "animation",
    "walk",
    "anime",
    "rpg",
}

SAFE_TERMS = {
    "safe",
    "sfw",
    "general audiences",
    "everyone",
    "all ages",
}

MIN_PNG_BYTES = 1_024
API_URL = "https://commons.wikimedia.org/w/api.php"
OGA_SEARCH_URL = "https://opengameart.org/search/node"
ITCH_SEARCH_URL = "https://itch.io/search"
USER_AGENT = "WaifuMon-WaifuDrone/2.0"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

GITHUB_CC0_SOURCES = (
    (
        "https://github.com/SpriteCook/spritecook-free-game-assets",
        "master",
        "examples/detailed-characters-anime/battleworn_knight.png",
    ),
    (
        "https://github.com/SpriteCook/spritecook-free-game-assets",
        "master",
        "examples/detailed-characters-anime/clockwork_owl.png",
    ),
    (
        "https://github.com/SpriteCook/spritecook-free-game-assets",
        "master",
        "examples/detailed-characters-anime/deepsea_knight.png",
    ),
    (
        "https://github.com/SpriteCook/spritecook-free-game-assets",
        "master",
        "examples/detailed-characters-anime/forest_archer.png",
    ),
    (
        "https://github.com/SpriteCook/spritecook-free-game-assets",
        "master",
        "examples/detailed-characters-anime/frog_paladin.png",
    ),
    (
        "https://github.com/SpriteCook/spritecook-free-game-assets",
        "master",
        "examples/detailed-characters-anime/gnome_merchant.png",
    ),
    (
        "https://github.com/SpriteCook/spritecook-free-game-assets",
        "master",
        "examples/detailed-characters-anime/monster_hunter.png",
    ),
    (
        "https://github.com/SpriteCook/spritecook-free-game-assets",
        "master",
        "examples/detailed-characters-anime/mouse_knight.png",
    ),
    (
        "https://github.com/SpriteCook/spritecook-free-game-assets",
        "master",
        "examples/detailed-characters-anime/mushroom_druid.png",
    ),
    (
        "https://github.com/SpriteCook/spritecook-free-game-assets",
        "master",
        "examples/detailed-characters-anime/noble_vampire.png",
    ),
)


def generate_asset_id(url: str) -> str:
    return "spr_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]


def _plain(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("value", "")
    return re.sub(r"<[^>]+>", " ", str(value or ""))


def _normalize_license(value: object) -> str:
    return " ".join(_plain(value).strip().casefold().split())


def _is_allowed_license(value: object) -> bool:
    normalized = _normalize_license(value)
    return normalized in ALLOWED_LICENSES or normalized.startswith("creative commons zero")


def _metadata(page: dict) -> str:
    info = (page.get("imageinfo") or [{}])[0]
    ext = info.get("extmetadata") or {}
    return " ".join(
        [
            _plain(page.get("title")),
            _plain(page.get("description")),
            _plain(ext.get("ImageDescription")),
            _plain(ext.get("Categories")),
            _plain(ext.get("ObjectName")),
            _plain(ext.get("Credit")),
        ]
    ).casefold()


def _blocked_text(text: str) -> bool:
    haystack = text.casefold()
    return any(term in haystack for term in BLOCKED_TERMS)


def _relevant_text(text: str) -> bool:
    haystack = text.casefold()
    return any(term in haystack for term in REQUIRED_TERMS)


def _safe_screening_text(text: str) -> bool:
    return not _blocked_text(text)


def _safe_rating_from_text(text: str) -> str:
    haystack = text.casefold()
    for term in SAFE_TERMS:
        if term in haystack:
            return "safe"
    return "unspecified"


def _license_from_page(page: dict) -> str:
    info = (page.get("imageinfo") or [{}])[0]
    ext = info.get("extmetadata") or {}
    for key in (
        "LicenseShortName",
        "UsageTerms",
        "License",
        "LicenseUrl",
    ):
        value = ext.get(key, "")
        if _is_allowed_license(value):
            return _plain(value).strip()
    return ""


def _png_dimensions_and_alpha(data: bytes) -> tuple[int, int, bool]:
    if len(data) < 33 or not data.startswith(PNG_SIGNATURE) or data[12:16] != b"IHDR":
        raise ValueError("invalid PNG signature/IHDR")
    width, height, bit_depth, color_type = struct.unpack(">IIBB", data[16:26])
    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions are invalid")
    if bit_depth not in {8, 16}:
        raise ValueError("unsupported PNG bit depth")
    alpha = color_type in {4, 6}
    cursor = 8
    while cursor + 12 <= len(data):
        length = struct.unpack(">I", data[cursor:cursor + 4])[0]
        chunk_type = data[cursor + 4:cursor + 8]
        cursor += 8
        end = cursor + length
        if end + 4 > len(data):
            break
        if chunk_type == b"tRNS":
            alpha = True
        cursor = end + 4
        if chunk_type == b"IEND":
            break
    return width, height, alpha


def _valid_png(data: bytes) -> tuple[int, int]:
    width, height, alpha = _png_dimensions_and_alpha(data)
    if len(data) < MIN_PNG_BYTES:
        raise ValueError("PNG is too small")
    if not alpha:
        raise ValueError("PNG has no transparency channel")
    return width, height


def _fetch_text(url: str, *, accept: str = "text/html") -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", "replace")


def _api_get(params: dict[str, str]) -> dict:
    query = urllib.parse.urlencode(params)
    return json.loads(
        _fetch_text(API_URL + "?" + query, accept="application/json")
    )


def _oga_search_urls(tag: str) -> list[str]:
    query = urllib.parse.urlencode({"keys": tag})
    html = _fetch_text(f"{OGA_SEARCH_URL}?{query}")
    matches = re.findall(r'href=["\'](/content/[^"\'#?]+)', html, re.IGNORECASE)
    return list(dict.fromkeys("https://opengameart.org" + item for item in matches))


def _oga_candidates_from_page(page_url: str) -> list[dict]:
    html = _fetch_text(page_url)
    head = re.split(r"Files?|Comments?", html, maxsplit=1, flags=re.IGNORECASE)[0]
    if not re.search(r"license[^<]{0,100}(CC0|public domain|MIT)", head, re.IGNORECASE):
        return []
    if _blocked_text(head):
        return []

    links = re.findall(
        r'href=["\']([^"\']+\.png(?:\?[^"\']*)?)["\']',
        html,
        re.IGNORECASE,
    )
    candidates = []
    for link in links:
        url = urllib.parse.urljoin(page_url, link)
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc != "opengameart.org":
            continue
        if not parsed.path.casefold().endswith(".png"):
            continue
        title = Path(parsed.path).name
        text = " ".join((page_url, title, head))
        if _blocked_text(text) or not _relevant_text(text):
            continue
        candidates.append(
            {
                "title": title,
                "source_page": page_url,
                "source_url": url,
                "license": "CC0",
                "safe_rating": "safe",
                "source": "opengameart",
            }
        )
    return candidates


def _oga_candidates() -> list[dict]:
    candidates = []
    seen_pages = set()
    for tag in SEARCH_TAGS:
        try:
            pages = _oga_search_urls(tag)
        except Exception as exc:
            print(f"[OGA SEARCH] {tag}: {exc}")
            continue
        for page_url in pages:
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            try:
                candidates.extend(_oga_candidates_from_page(page_url))
            except Exception as exc:
                print(f"[OGA PAGE] {page_url}: {exc}")
    return candidates


def _itch_search_projects(tag: str) -> list[str]:
    query = urllib.parse.urlencode({"q": tag})
    html = _fetch_text(f"{ITCH_SEARCH_URL}?{query}")
    matches = re.findall(
        r'href=["\'](https?://[^"\']+\.itch\.io/[^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    return list(dict.fromkeys(matches))


def _itch_candidates() -> list[dict]:
    candidates = []
    seen_pages = set()
    for tag in SEARCH_TAGS:
        try:
            pages = _itch_search_projects(tag)
        except Exception as exc:
            print(f"[ITCH SEARCH] {tag}: {exc}")
            continue
        for page_url in pages:
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            try:
                html = _fetch_text(page_url)
            except Exception as exc:
                print(f"[ITCH PAGE] {page_url}: {exc}")
                continue

            lower = html.casefold()
            if _blocked_text(lower):
                continue
            if not any(
                marker in lower
                for marker in (
                    "creative commons zero",
                    "cc0",
                    "mit license",
                    "public domain",
                )
            ):
                continue

            safe_rating = _safe_rating_from_text(lower)
            if safe_rating != "safe":
                continue

            license_value = "CC0"
            if "mit license" in lower and "cc0" not in lower:
                license_value = "MIT"

            links = re.findall(
                r'href=["\']([^"\']+\.png(?:\?[^"\']*)?)["\']',
                html,
                re.IGNORECASE,
            )
            for link in links:
                url = urllib.parse.urljoin(page_url, link)
                parsed = urllib.parse.urlparse(url)
                if not parsed.path.casefold().endswith(".png"):
                    continue
                title = Path(parsed.path).name
                text = " ".join((page_url, title, lower))
                if _blocked_text(text) or not _relevant_text(text):
                    continue
                candidates.append(
                    {
                        "title": title,
                        "source_page": page_url,
                        "source_url": url,
                        "license": license_value,
                        "safe_rating": safe_rating,
                        "source": "itch",
                    }
                )
    return candidates


def _commons_candidates(target_amount: int) -> list[dict]:
    candidates = []
    seen = set()
    for tag in SEARCH_TAGS:
        try:
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
        except Exception as exc:
            print(f"[COMMONS SEARCH] {tag}: {exc}")
            continue

        for page in data.get("query", {}).get("pages", []):
            info_list = page.get("imageinfo") or []
            if not info_list:
                continue
            info = info_list[0]
            url = str(info.get("url") or "").strip()
            mime = str(info.get("mime") or "").casefold()
            if not url or url in seen:
                continue
            seen.add(url)
            if mime != "image/png" or not urllib.parse.urlparse(url).path.casefold().endswith(".png"):
                continue

            license_value = _license_from_page(page)
            if not license_value or not _is_allowed_license(license_value):
                continue

            metadata = _metadata(page)
            if _blocked_text(metadata) or not _relevant_text(metadata):
                continue

            rating = _safe_rating_from_text(metadata)
            if rating not in {"safe", "unspecified"}:
                continue

            size = int(info.get("size") or 0)
            if size < MIN_PNG_BYTES:
                continue

            title = str(page.get("title", "")).strip()
            source_page = (
                "https://commons.wikimedia.org/wiki/"
                + urllib.parse.quote(title.replace(" ", "_"), safe=":/_(),.-")
            )
            candidates.append(
                {
                    "title": title,
                    "source_page": source_page,
                    "source_url": url,
                    "license": license_value,
                    "safe_rating": rating,
                    "source": "wikimedia",
                }
            )
            if len(candidates) >= target_amount * 4:
                return candidates
    return candidates


def _github_candidates() -> list[dict]:
    return [
        {
            "title": Path(path).name,
            "source_page": repo_url + "/tree/" + branch + "/" + urllib.parse.quote(path, safe="/"),
            "source_url": (
                "https://raw.githubusercontent.com/"
                + repo_url.removeprefix("https://github.com/")
                + "/"
                + branch
                + "/"
                + urllib.parse.quote(path, safe="/")
            ),
            "license": "CC0-1.0",
            "safe_rating": "safe",
            "source": "github-cc0-repo",
        }
        for repo_url, branch, path in GITHUB_CC0_SOURCES
    ]


def _download_png(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "image/png,application/octet-stream"},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read()
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].casefold()
                if content_type not in {"image/png", "application/octet-stream"}:
                    raise ValueError(f"unexpected content type: {content_type!r}")
                width, height = _valid_png(data)
                return data, f"{width}x{height}"
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 3:
                raise
            retry_after = exc.headers.get("Retry-After", "")
            try:
                delay = max(3.0, float(retry_after))
            except ValueError:
                delay = 3.0 * (2 ** attempt)
            print(f"[RADAR] rate limit; retrying in {delay:.1f}s")
            time.sleep(delay)
    raise RuntimeError("unreachable download state")


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    body = chunk_type + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _make_offline_sprite(seed: int) -> bytes:
    """Create an original transparent pixel sprite when network access is unavailable."""
    width, height, scale = 16, 24, 4
    palettes = (
        ((27, 24, 46, 255), (112, 70, 120, 255), (245, 205, 174, 255), (78, 134, 196, 255), (214, 100, 146, 255)),
        ((24, 35, 48, 255), (70, 124, 146, 255), (238, 194, 160, 255), (64, 160, 136, 255), (232, 164, 72, 255)),
        ((31, 27, 22, 255), (116, 73, 47, 255), (243, 208, 178, 255), (118, 84, 170, 255), (72, 148, 94, 255)),
        ((20, 28, 49, 255), (74, 82, 150, 255), (239, 196, 168, 255), (92, 158, 202, 255), (228, 102, 100, 255)),
        ((34, 24, 28, 255), (152, 61, 78, 255), (244, 204, 172, 255), (106, 78, 176, 255), (196, 112, 54, 255)),
    )
    colors = palettes[seed % len(palettes)]
    bg = (0, 0, 0, 0)
    pixels = [[bg for _ in range(width)] for _ in range(height)]

    def rect(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int, int]) -> None:
        for y in range(max(0, y0), min(height, y1)):
            for x in range(max(0, x0), min(width, x1)):
                pixels[y][x] = color

    hair, outfit, skin, accent, secondary = colors
    rect(5, 2, 11, 4, hair)
    rect(4, 3, 12, 8, hair)
    rect(5, 6, 11, 11, skin)
    rect(4, 7, 6, 13, hair)
    rect(10, 7, 12, 13, hair)
    rect(5, 9, 7, 10, (52, 48, 70, 255))
    rect(9, 9, 11, 10, (52, 48, 70, 255))
    rect(6, 12, 10, 17, outfit)
    rect(4, 13, 6, 17, skin)
    rect(10, 13, 12, 17, skin)
    rect(5, 16, 11, 19, secondary if seed % 2 else accent)
    rect(4, 18, 12, 20, accent)
    rect(5, 20, 7, 23, hair)
    rect(9, 20, 11, 23, hair)
    rect(6, 17, 10, 18, accent)
    if seed % 3 == 0:
        rect(12, 4, 14, 6, accent)
        rect(13, 3, 14, 5, accent)
    elif seed % 3 == 1:
        rect(2, 5, 4, 7, secondary)
        rect(2, 4, 3, 6, secondary)
    else:
        rect(12, 10, 14, 12, accent)
        rect(13, 9, 14, 11, accent)

    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for r, g, b, a in row:
            raw.extend((r, g, b, a))

    ihdr = struct.pack(">IIBBBBB", width * scale, height * scale, 8, 6, 0, 0, 0)
    expanded = bytearray()
    for y in range(height):
        row = pixels[y]
        for _ in range(scale):
            expanded.append(0)
            for pixel in row:
                expanded.extend(pixel * scale)
    compressed = zlib.compress(bytes(expanded), level=9)
    return PNG_SIGNATURE + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", compressed) + _png_chunk(b"IEND", b"")


def _record_rejected(records: list[dict], item: dict, reason: str) -> None:
    records.append(
        {
            "title": item.get("title", ""),
            "source_page": item.get("source_page", ""),
            "source_url": item.get("source_url", ""),
            "license": item.get("license", ""),
            "reason": reason,
        }
    )


def _load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _sanitize_existing() -> tuple[list[Path], list[dict]]:
    accepted = []
    rejected = _load_records(MANIFEST_FILE)
    by_file = {
        str(record.get("file", "")): record
        for record in rejected
        if isinstance(record, dict)
    }

    for path in sorted(RAW_SPRITE_DIR.glob("*.png")):
        record = by_file.get(path.as_posix())
        if record is None:
            path.unlink(missing_ok=True)
            continue
        license_value = record.get("license", "")
        if not _is_allowed_license(license_value):
            path.unlink(missing_ok=True)
            _record_rejected(rejected, record, "license_not_allowed")
            continue
        if _blocked_text(" ".join(str(record.get(key, "")) for key in ("title", "source_page", "source_url"))):
            path.unlink(missing_ok=True)
            _record_rejected(rejected, record, "blocked_metadata")
            continue
        try:
            _valid_png(path.read_bytes())
        except (OSError, ValueError) as exc:
            path.unlink(missing_ok=True)
            _record_rejected(rejected, record, f"invalid_png:{exc}")
            continue
        accepted.append(path)
    return accepted, rejected


def fetch_cc0_waifus(target_amount: int = 10) -> int:
    if target_amount < 1:
        raise ValueError("target_amount must be positive")

    RAW_SPRITE_DIR.mkdir(parents=True, exist_ok=True)
    PROD_SPRITE_DIR.mkdir(parents=True, exist_ok=True)

    existing_files, rejected_records = _sanitize_existing()
    if len(existing_files) >= target_amount:
        print(f"=== CUOTA YA CUMPLIDA: {len(existing_files)}/{target_amount} PNG VÁLIDOS ===")
        return len(existing_files)

    candidates = _github_candidates()
    try:
        candidates.extend(_oga_candidates())
    except Exception as exc:
        print(f"[OGA] search unavailable: {exc}")
    try:
        candidates.extend(_itch_candidates())
    except Exception as exc:
        print(f"[ITCH] search unavailable: {exc}")
    try:
        candidates.extend(_commons_candidates(target_amount))
    except Exception as exc:
        print(f"[COMMONS] search unavailable: {exc}")

    seen = {item.get("source_url") for item in candidates}
    accepted_count = len(existing_files)
    records = _load_records(MANIFEST_FILE)

    for item in candidates:
        if accepted_count >= target_amount:
            break
        source_url = str(item.get("source_url", ""))
        if not source_url or source_url in seen and any(
            record.get("source_url") == source_url for record in records
        ):
            continue
        seen.add(source_url)

        license_value = item.get("license", "")
        metadata_text = " ".join(
            str(item.get(key, ""))
            for key in ("title", "source_page", "source_url", "safe_rating")
        )
        if not _is_allowed_license(license_value):
            _record_rejected(rejected_records, item, "license_not_allowed")
            continue
        if _blocked_text(metadata_text):
            _record_rejected(rejected_records, item, "blocked_metadata")
            continue
        if not _relevant_text(metadata_text):
            _record_rejected(rejected_records, item, "not_character_relevant")
            continue
        if str(item.get("source")) == "itch" and item.get("safe_rating") != "safe":
            _record_rejected(rejected_records, item, "safe_rating_required")
            continue

        asset_id = generate_asset_id(source_url)
        destination = RAW_SPRITE_DIR / f"{asset_id}_raw.png"
        if destination.exists():
            continue

        print(f"[INTERCEPTANDO] {item.get('title', source_url)}")
        try:
            data, dimensions = _download_png(source_url)
            destination.write_bytes(data)
            records.append(
                {
                    "asset_id": asset_id,
                    "file": destination.as_posix(),
                    "source_page": item["source_page"],
                    "source_url": source_url,
                    "license": license_value,
                    "mime": "image/png",
                    "dimensions": dimensions,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "safe_rating": item.get("safe_rating", "unspecified"),
                    "watermark_screen": "pass:metadata-only",
                    "status": "quarantine_only",
                }
            )
            accepted_count += 1
            print(f"[OK] {destination.as_posix()} {dimensions}")
            time.sleep(0.5)
        except Exception as exc:
            destination.unlink(missing_ok=True)
            _record_rejected(rejected_records, item, f"download_rejected:{exc}")
            print(f"[SKIP] {source_url}: {exc}")

    if accepted_count < target_amount:
        missing = target_amount - accepted_count
        print(
            f"[OFFLINE FALLBACK] {missing} PNG originales transparentes CC0 "
            "serán creados porque no se pudieron obtener suficientes recursos remotos."
        )
        for index in range(missing):
            seed = accepted_count + index
            data = _make_offline_sprite(seed)
            asset_id = f"spr_local_cc0_{seed + 1:02d}"
            destination = RAW_SPRITE_DIR / f"{asset_id}_raw.png"
            destination.write_bytes(data)
            width, height = _valid_png(data)
            source_page = "local://waifu-drone/offline-original"
            source_url = f"local://waifu-drone/offline-original/{asset_id}"
            records.append(
                {
                    "asset_id": asset_id,
                    "file": destination.as_posix(),
                    "source_page": source_page,
                    "source_url": source_url,
                    "license": "CC0-1.0",
                    "mime": "image/png",
                    "dimensions": f"{width}x{height}",
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "safe_rating": "safe",
                    "watermark_screen": "pass:original-no-overlay",
                    "status": "quarantine_only",
                    "provenance": "original_local_fallback",
                }
            )
            accepted_count += 1

    MANIFEST_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REJECTED_MANIFEST_FILE.write_text(
        json.dumps(rejected_records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"=== {accepted_count}/{target_amount} PNG EN CUARENTENA ===")
    return accepted_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="WaifuMon CC0/public-domain sprite drone"
    )
    parser.add_argument("--target-amount", type=int, default=10)
    args = parser.parse_args()
    raise SystemExit(0 if fetch_cc0_waifus(args.target_amount) >= args.target_amount else 1)
