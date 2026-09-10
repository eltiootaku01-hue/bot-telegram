import pytest

from app.game.evolution import can_fuse, consume_for_fusion, next_fusion


@pytest.mark.parametrize(
    ("rarity", "required", "next_rarity"),
    [("D", 10, "C"), ("C", 40, "B"), ("B", 60, "A"), ("A", 80, "S")],
)
def test_fusion_rules(rarity: str, required: int, next_rarity: str) -> None:
    rule = next_fusion(rarity)
    assert rule is not None
    assert rule.copies_required == required
    assert rule.to_rarity == next_rarity
    assert can_fuse(rarity, required)
    assert not can_fuse(rarity, required - 1)


def test_consume_for_fusion_keeps_remainder() -> None:
    rule, remaining = consume_for_fusion("D", 13)
    assert rule.to_rarity == "C"
    assert remaining == 3


def test_s_has_no_next_fusion() -> None:
    assert next_fusion("S") is None
