from __future__ import annotations

import sys
from pathlib import Path


def resolve_asset(repository_path: str) -> Path | None:
    """Resolve a bundled asset from source checkout, CWD or PyInstaller extraction."""
    relative = Path(repository_path)
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / relative)
    candidates.append(Path.cwd() / relative)
    candidates.append(Path(__file__).resolve().parents[2] / relative)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None
