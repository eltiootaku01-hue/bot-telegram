from app.services.telegram_setup import (
    ROLE_ADMIN_RIGHTS,
    build_group_add_link,
    build_private_link,
    required_group_rights,
)


def test_group_add_link_is_bot_specific_and_encodes_role_permissions() -> None:
    link = build_group_add_link("@ChieBot", role="chie")

    assert link.startswith("https://t.me/ChieBot?startgroup=bottelegram")
    assert "admin=delete_messages%2Brestrict_members%2Bmanage_topics" in link


def test_sunna_group_add_link_does_not_request_admin_rights() -> None:
    link = build_group_add_link("SunnaBot", role="sunna")

    assert link == "https://t.me/SunnaBot?startgroup=bottelegram"
    assert required_group_rights("sunna") == ROLE_ADMIN_RIGHTS["sunna"] == ()


def test_private_link_normalizes_username() -> None:
    assert build_private_link("@CariBot") == "https://t.me/CariBot"
