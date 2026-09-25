from __future__ import annotations

import argparse
import io
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CARD_SIZE = (1024, 1536)
RARITY_STYLES = {
    "C": {"accent": (235, 240, 248, 255)},
    "R": {"accent": (190, 225, 255, 255)},
    "SR": {"accent": (235, 200, 255, 255)},
    "SSR": {"accent": (255, 235, 150, 255)},
    "UR": {"accent": (255, 185, 220, 255)},
}
ELEMENT_GLYPHS = {"fire": "F", "water": "W", "wind": "A", "earth": "E", "light": "L", "dark": "D", "electric": "⚡", "ice": "❄"}


@dataclass(frozen=True, slots=True)
class CardRenderRequest:
    name: str
    element: str
    rarity: str
    edition: str
    render: Path | None = None
    render_url: str | None = None


class CardBuilder:
    """Deterministic layered card compositor with local/API render ingestion."""

    def __init__(self, *, font_path: str | Path | None = None) -> None:
        self.font_path = Path(font_path) if font_path else None

    def _font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = [self.font_path] if self.font_path else []
        candidates += [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")]
        for candidate in candidates:
            if candidate and candidate.is_file():
                return ImageFont.truetype(str(candidate), size)
        return ImageFont.load_default()

    def ingest_render(self, source: str | Path) -> Image.Image:
        """Load a transparent PNG from local disk or an HTTP(S) image URL."""
        if str(source).startswith(("http://", "https://")):
            request = urllib.request.Request(str(source), headers={"User-Agent": "bot-telegram-card-builder/1.0"})
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = response.read()
            image = Image.open(io.BytesIO(payload))
        else:
            image = Image.open(Path(source))
        image.load()
        return image.convert("RGBA")

    def fetch_anilist_character(self, character_id: int) -> Image.Image:
        query = "query ($id: Int) { Character(id: $id) { image { large } } }"
        payload = json.dumps({"query": query, "variables": {"id": character_id}}).encode()
        request = urllib.request.Request("https://graphql.anilist.co", data=payload, headers={"Content-Type": "application/json", "User-Agent": "bot-telegram-card-builder/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        return self.ingest_render(data["data"]["Character"]["image"]["large"])

    def fetch_mal_character(self, character_id: int) -> Image.Image:
        request = urllib.request.Request(f"https://api.jikan.moe/v4/characters/{character_id}", headers={"User-Agent": "bot-telegram-card-builder/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        return self.ingest_render(data["data"]["images"]["jpg"]["image_url"])

    def _element_emblem(self, element: str, size: int, accent: tuple[int, int, int, int]) -> Image.Image:
        emblem = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(emblem)
        center = size // 2
        draw.ellipse((4, 4, size - 4, size - 4), fill=(10, 14, 25, 215), outline=accent, width=max(3, size // 24))
        glyph = ELEMENT_GLYPHS.get(element.casefold(), element[:1].upper() or "?")
        font = self._font(max(20, size // 3))
        bbox = draw.textbbox((0, 0), glyph, font=font)
        draw.text((center - (bbox[2] - bbox[0]) / 2, center - (bbox[3] - bbox[1]) / 2 - bbox[1]), glyph, font=font, fill=accent)
        return emblem

    def _frame(self, rarity: str, accent: tuple[int, int, int, int]) -> Image.Image:
        layer = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        width = {"C": 18, "R": 24, "SR": 30, "SSR": 38, "UR": 46}[rarity]
        for inset in range(0, width, max(4, width // 5)):
            draw.rounded_rectangle((inset, inset, CARD_SIZE[0] - inset - 1, CARD_SIZE[1] - inset - 1), radius=52, outline=(*accent[:3], max(55, 230 - inset * 4)), width=max(2, width // 8))
        return layer

    def build(self, request: CardRenderRequest, output: str | Path) -> Path:
        rarity = request.rarity.upper()
        if rarity not in RARITY_STYLES:
            raise ValueError(f"unsupported rarity: {request.rarity}")
        if not request.edition.startswith("#") or not request.edition[1:].isdigit():
            raise ValueError("edition must look like #001")
        if request.render is not None:
            character = self.ingest_render(request.render)
        elif request.render_url:
            character = self.ingest_render(request.render_url)
        else:
            raise ValueError("a local render or render_url is required")

        character.thumbnail((900, 1240), Image.Resampling.LANCZOS)
        accent = RARITY_STYLES[rarity]["accent"]
        canvas = Image.new("RGBA", CARD_SIZE, (13, 17, 29, 255))
        x = (CARD_SIZE[0] - character.width) // 2
        y = 100 + (1180 - character.height) // 2
        # Layer order: background -> element emblem -> transparent character render -> frame -> typography.
        emblem = self._element_emblem(request.element, 190, accent)
        canvas.alpha_composite(emblem, ((CARD_SIZE[0] - emblem.width) // 2, 560))
        canvas.alpha_composite(character, (x, y))
        canvas.alpha_composite(self._frame(rarity, accent))

        draw = ImageDraw.Draw(canvas)
        name_font, edition_font, rarity_font = self._font(64), self._font(42), self._font(34)
        footer_y = 1370
        draw.rounded_rectangle((55, footer_y, CARD_SIZE[0] - 55, 1500), radius=28, fill=(8, 11, 20, 225), outline=accent, width=3)
        draw.text((90, footer_y + 18), request.name[:28], font=name_font, fill=accent)
        draw.text((90, footer_y + 88), f"{request.edition}  •  {request.element.upper()}", font=edition_font, fill=(245, 245, 250, 255))
        bbox = draw.textbbox((0, 0), rarity, font=rarity_font)
        draw.text((CARD_SIZE[0] - 90 - (bbox[2] - bbox[0]), footer_y + 34), rarity, font=rarity_font, fill=accent)

        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(target, "PNG", optimize=True)
        return target


def build_test_card(output: str | Path) -> Path:
    """Create a self-contained smoke-test card without remote artwork."""
    source = Image.new("RGBA", (700, 1000), (0, 0, 0, 0))
    draw = ImageDraw.Draw(source)
    draw.ellipse((150, 90, 550, 490), fill=(235, 180, 210, 255))
    draw.rounded_rectangle((230, 420, 470, 900), radius=80, fill=(100, 120, 200, 255))
    temp = Path(output).with_suffix(".source.png")
    temp.parent.mkdir(parents=True, exist_ok=True)
    source.save(temp, "PNG")
    try:
        return CardBuilder().build(CardRenderRequest("Render de Prueba", "fire", "UR", "#001", render=temp), output)
    finally:
        temp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Layered anime card renderer")
    parser.add_argument("--render")
    parser.add_argument("--render-url")
    parser.add_argument("--name", default="Render de Prueba")
    parser.add_argument("--element", default="fire")
    parser.add_argument("--rarity", default="UR")
    parser.add_argument("--edition", default="#001")
    parser.add_argument("--output", default="data/card_test/card-001.png")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        build_test_card(args.output)
    else:
        CardBuilder().build(CardRenderRequest(args.name, args.element, args.rarity, args.edition, Path(args.render) if args.render else None, args.render_url), args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
