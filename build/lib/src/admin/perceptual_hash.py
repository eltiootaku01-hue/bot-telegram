from __future__ import annotations

from imagehash import hex_to_hash


def is_perceptual_duplicate(
    new_phash_str: str,
    existing_hashes: list[str],
    max_distance: int = 4,
) -> tuple[bool, int]:
    """Return whether a pHash is within ``max_distance`` Hamming bits."""
    if max_distance < 0:
        raise ValueError("max_distance must be non-negative")

    new_hash = hex_to_hash(new_phash_str)
    min_distance: int | None = None

    for existing_hash_str in existing_hashes:
        existing_hash = hex_to_hash(existing_hash_str)
        distance = int(new_hash - existing_hash)
        if min_distance is None or distance < min_distance:
            min_distance = distance
        if distance <= max_distance:
            return True, distance

    return False, -1 if min_distance is None else min_distance
