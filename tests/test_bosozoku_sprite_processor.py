from pathlib import Path

from PIL import Image

from tools.process_bosozoku_sprite import MUGEN_MAGENTA, TINT_COLOR, process_sprite


def test_bosozoku_sprite_processor_clears_magenta_and_preserves_alpha(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    destination = tmp_path / "production" / "sprite.png"

    with Image.new("RGBA", (2, 1), MUGEN_MAGENTA + (255,)) as image:
        image.putpixel((1, 0), (10, 20, 30, 255))
        image.save(source, "PNG")

    changed, pixels = process_sprite(
        source,
        destination,
        contrast=1.0,
        saturation=1.0,
    )

    assert changed == 1
    assert pixels == 2

    with Image.open(destination) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0

        expected_red = int((10 + TINT_COLOR[0]) / 2)
        assert image.getpixel((1, 0)) == (expected_red, 20, 30, 255)


def test_bosozoku_processor_writes_png_to_requested_destination(tmp_path: Path) -> None:
    source = tmp_path / "source.bmp"
    destination = tmp_path / "nested" / "sprite.png"

    with Image.new("RGB", (4, 4), (25, 25, 25)) as image:
        image.save(source, "BMP")

    changed, pixels = process_sprite(source, destination)

    assert changed == 0
    assert pixels == 16
    assert destination.is_file()
    assert destination.suffix == ".png"
