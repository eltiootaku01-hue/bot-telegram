from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FusionRule:
    """Copies of the current rank required to create the next rank."""

    from_rarity: str
    to_rarity: str
    copies_required: int


# Tuneable game economy. The final S rank is intentionally expensive.
FUSION_RULES: tuple[FusionRule, ...] = (
    FusionRule("D", "C", 10),
    FusionRule("C", "B", 40),
    FusionRule("B", "A", 60),
    FusionRule("A", "S", 80),
)


def next_fusion(rarity: str) -> FusionRule | None:
    normalized = rarity.upper()
    return next((rule for rule in FUSION_RULES if rule.from_rarity == normalized), None)


def can_fuse(rarity: str, copies: int) -> bool:
    rule = next_fusion(rarity)
    return rule is not None and copies >= rule.copies_required


def consume_for_fusion(rarity: str, copies: int) -> tuple[FusionRule, int]:
    """Validate a fusion and return the rule plus remaining copies."""
    rule = next_fusion(rarity)
    if rule is None:
        raise ValueError(f"No fusion rule exists for rarity {rarity!r}")
    if copies < rule.copies_required:
        raise ValueError(f"Need {rule.copies_required} copies of {rarity}, have {copies}")
    return rule, copies - rule.copies_required
