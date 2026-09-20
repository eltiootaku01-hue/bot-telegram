from __future__ import annotations

import re


TIO_ADDRESS_RE = re.compile(
    r"(?i)(?:^|[!?.,;:]\s*)t(?:í|i)o(?:\s+otaku)?(?=\s*(?:[,;:!?]|$))"
)


def is_tio_addressed(text: str) -> bool:
    """Return whether text explicitly uses Tío/Tío Otaku as a vocative."""
    normalized = " ".join(text.strip().split())
    return bool(normalized and TIO_ADDRESS_RE.search(normalized))
