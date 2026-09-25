from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import imagehash
from PIL import Image, ImageOps, UnidentifiedImageError

@dataclass(frozen=True, slots=True)
class ProcessedAsset:
    path: Path
    width: int
    height: int
    mime_type: str
    phash: str

class ImageProcessor:
    """Normalize card assets to a deterministic 512x768 WebP representation."""
    def __init__(self, output_dir: str | Path = "data/card_assets/normalized") -> None:
        self.output_dir = Path(output_dir)

    def process(self, source: str | Path, *, output_name: str) -> ProcessedAsset:
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(source)
        try:
            with Image.open(source) as image:
                image.load()
                normalized = ImageOps.fit(image.convert("RGB"), (512, 768), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("asset is not a readable image") from exc
        self.output_dir.mkdir(parents=True, exist_ok=True)
        target = self.output_dir / f"{output_name}.webp"
        normalized.save(target, "WEBP", quality=88, method=6)
        return ProcessedAsset(target, 512, 768, "image/webp", str(imagehash.phash(normalized)))
