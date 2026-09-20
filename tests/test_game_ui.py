from app.ui.game_keyboards import game_hub_keyboard


def test_game_hub_exposes_daily_missions_action() -> None:
    markup = game_hub_keyboard()
    data = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]

    assert "game:missions:open" in data
