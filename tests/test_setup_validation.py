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
