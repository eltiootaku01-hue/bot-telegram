from __future__ import annotations

import argparse
from pathlib import Path

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - exercised by CLI users
    raise SystemExit(
        "Pillow is required. Install with: python -m pip install 'Pillow>=11,<13'"
    ) from exc


MAGENTA = (255, 0, 255)


def make_magenta_transparent(source: Path, destination: Path) -> int:
    with Image.open(source) as image:
        rgba = image.convert("RGBA")
        pixels = rgba.load()
        changed = 0

        for y in range(rgba.height):
            for x in range(rgba.width):
                red, green, blue, alpha = pixels[x, y]
                if (red, green, blue) == MAGENTA and alpha:
                    pixels[x, y] = (red, green, blue, 0)
                    changed += 1

        destination.parent.mkdir(parents=True, exist_ok=True)
        rgba.save(destination, format="PNG", optimize=True)
        return changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convierte #FF00FF a alpha=0 en un PNG con licencia compatible. "
            "No descarga ni obtiene assets por sí mismo."
        )
    )
    parser.add_argument("source", type=Path, help="PNG de entrada legalmente adquirido")
    parser.add_argument("destination", type=Path, help="PNG RGBA de salida")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.source.is_file():
        raise SystemExit(f"Source file does not exist: {args.source}")
    if args.source.suffix.lower() != ".png":
        raise SystemExit("Source must be a PNG file")

    changed = make_magenta_transparent(args.source, args.destination)
    print(f"Converted {changed} magenta pixels: {args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
