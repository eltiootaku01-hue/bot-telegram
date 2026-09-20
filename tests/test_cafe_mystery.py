from app.services.cafe_mystery import CAFE_MYSTERIES, mystery_for


def test_cafe_mysteries_are_valid_and_have_distinct_keys() -> None:
    assert len(CAFE_MYSTERIES) >= 5
    assert len({item.key for item in CAFE_MYSTERIES}) == len(CAFE_MYSTERIES)
    assert all(0 <= item.answer_index < len(item.options) for item in CAFE_MYSTERIES)


def test_mystery_selection_is_deterministic_per_day_and_chat() -> None:
    first = mystery_for("2026-09-20", -100)
    second = mystery_for("2026-09-20", -100)
    other_day = mystery_for("2026-09-21", -100)

    assert first == second
    assert first in CAFE_MYSTERIES
    assert other_day in CAFE_MYSTERIES


def test_mystery_can_change_with_chat_without_random_runtime_state() -> None:
    selections = {mystery_for("2026-09-20", chat_id) for chat_id in range(-100, -80)}
    assert selections
