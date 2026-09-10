from app.ui.media_keyboards import cami_media_actions, cami_publish_destination


def test_cami_media_actions_expose_only_private_workflow_actions() -> None:
    markup = cami_media_actions(7)
    data = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert "cami:media:tag:7" in data
    assert "cami:media:schedule:7" in data
    assert "cami:media:archive:7" in data


def test_cami_destination_keeps_page_and_group_linked() -> None:
    markup = cami_publish_destination(7)
    data = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert "cami:media:dest:both:7" in data
    assert "cami:media:dest:group:7" in data
