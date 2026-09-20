from app.services.setup_validation import parse_numeric_ids, validate_setup


def _bots() -> dict[str, dict[str, str]]:
    return {
        name: {"link": f"https://t.me/{name}", "token": f"token-{name}"}
        for name in ("cari", "sunna", "cami", "chie")
    }


def test_parse_numeric_ids_rejects_invalid_and_duplicate_values() -> None:
    values, errors = parse_numeric_ids("-100,-200,-100,nope", field_name="AUTHORIZED_CHAT_IDS")

    assert values == (-100, -200)
    assert "repetido" in errors[0]
    assert "no es un ID" in errors[1]


def test_validate_setup_rejects_bad_access_and_infrastructure_ids() -> None:
    result = validate_setup(
        bots=_bots(),
        authorized_chat_ids="-100,44",
        admin_user_id="admin",
        allow_admin_private_chat=True,
        allow_user_private_chat=False,
        media_storage_chat_id="bad",
        publish_page_chat_id="12",
    )

    assert not result.valid
    assert any("AUTHORIZED_CHAT_IDS" in error for error in result.errors)
    assert any("ADMIN_USER_ID" in error for error in result.errors)
    assert any("MEDIA_STORAGE_CHAT_ID" in error for error in result.errors)
    assert any("PUBLISH_PAGE_CHAT_ID" in error for error in result.errors)


def test_validate_setup_accepts_standard_local_configuration() -> None:
    result = validate_setup(
        bots=_bots(),
        authorized_chat_ids="-100123,-100456",
        admin_user_id="123456",
        allow_admin_private_chat=True,
        allow_user_private_chat=True,
        media_storage_chat_id="-100777",
        publish_page_chat_id="-100888",
        base_group_chat_id="-100123",
    )

    assert result.valid
    assert result.errors == ()


def test_validate_setup_warns_when_every_user_facing_surface_is_disabled() -> None:
    result = validate_setup(
        bots=_bots(),
        authorized_chat_ids="",
        admin_user_id="123456",
        allow_admin_private_chat=True,
        allow_user_private_chat=False,
        media_storage_chat_id="0",
        publish_page_chat_id="0",
    )

    assert result.valid
    assert result.warnings


def test_validate_setup_warns_when_base_group_is_not_authorized() -> None:
    result = validate_setup(
        bots=_bots(),
        authorized_chat_ids="-100456",
        admin_user_id="123456",
        allow_admin_private_chat=True,
        allow_user_private_chat=True,
        media_storage_chat_id="0",
        publish_page_chat_id="0",
        base_group_chat_id="-100123",
    )

    assert result.valid
    assert any("grupo base" in warning.casefold() for warning in result.warnings)


def test_validate_setup_rejects_positive_base_group_id() -> None:
    result = validate_setup(
        bots=_bots(),
        authorized_chat_ids="-100123",
        admin_user_id="123456",
        allow_admin_private_chat=True,
        allow_user_private_chat=True,
        media_storage_chat_id="0",
        publish_page_chat_id="0",
        base_group_chat_id="123",
    )

    assert not result.valid
    assert any("BASE_GROUP_CHAT_ID" in error for error in result.errors)


def test_validate_setup_allows_token_only_bot_configuration() -> None:
    bots = {
        name: {"link": "", "token": f"token-{name}"}
        for name in ("cari", "sunna", "cami", "chie")
    }
    result = validate_setup(
        bots=bots,
        authorized_chat_ids="-100123",
        admin_user_id="123456",
        allow_admin_private_chat=True,
        allow_user_private_chat=True,
        media_storage_chat_id="0",
        publish_page_chat_id="0",
        base_group_chat_id="-100123",
    )

    assert result.valid
    assert not result.errors
    assert all("enlace" in warning.casefold() for warning in result.warnings)


def test_validate_setup_rejects_invalid_chie_verification_controls() -> None:
    result = validate_setup(
        bots=_bots(),
        authorized_chat_ids="-100123",
        admin_user_id="123456",
        allow_admin_private_chat=True,
        allow_user_private_chat=True,
        media_storage_chat_id="0",
        publish_page_chat_id="0",
        base_group_chat_id="-100123",
        human_verification_timeout_seconds="29",
        human_verification_raid_window_seconds="0",
        human_verification_raid_threshold="nope",
        human_verification_raid_timeout_seconds="10",
    )

    assert not result.valid
    assert any("HUMAN_VERIFICATION_TIMEOUT_SECONDS" in error for error in result.errors)
    assert any("HUMAN_VERIFICATION_RAID_WINDOW_SECONDS" in error for error in result.errors)
    assert any("HUMAN_VERIFICATION_RAID_THRESHOLD" in error for error in result.errors)
    assert any("HUMAN_VERIFICATION_RAID_TIMEOUT_SECONDS" in error for error in result.errors)


def test_validate_setup_warns_when_raid_timeout_is_longer_than_normal() -> None:
    result = validate_setup(
        bots=_bots(),
        authorized_chat_ids="-100123",
        admin_user_id="123456",
        allow_admin_private_chat=True,
        allow_user_private_chat=True,
        media_storage_chat_id="0",
        publish_page_chat_id="0",
        base_group_chat_id="-100123",
        human_verification_timeout_seconds="60",
        human_verification_raid_window_seconds="60",
        human_verification_raid_threshold="5",
        human_verification_raid_timeout_seconds="90",
    )

    assert result.valid
    assert any("TTL" in warning for warning in result.warnings)
