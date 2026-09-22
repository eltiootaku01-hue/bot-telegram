from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageColor, ImageEnhance


MUGEN_MAGENTA = (255, 0, 255)
TINT_COLOR = ImageColor.getrgb("#b026ff")


def process_sprite(
    source: Path,
    destination: Path,
    *,
    contrast: float = 1.5,
    saturation: float = 1.3,
) -> tuple[int, int]:
    if contrast <= 0 or saturation < 0:
        raise ValueError("contrast must be > 0 and saturation must be >= 0")
    with Image.open(source) as original:
        image = original.convert("RGBA")
        pixels = image.load()
        magenta_pixels = 0

        for y in range(image.height):
            for x in range(image.width):
                red, green, blue, alpha = pixels[x, y]
                if alpha and (red, green, blue) == MUGEN_MAGENTA:
                    pixels[x, y] = (255, 255, 255, 0)
                    magenta_pixels += 1
                    continue

                tinted_red = int((red + TINT_COLOR[0]) / 2)
                pixels[x, y] = (
                    min(255, max(0, tinted_red)),
                    green,
                    blue,
                    alpha,
                )

        image = ImageEnhance.Contrast(image).enhance(contrast)
        image = ImageEnhance.Color(image).enhance(saturation)
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, "PNG", optimize=True)

        return magenta_pixels, image.width * image.height
