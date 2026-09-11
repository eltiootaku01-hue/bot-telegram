import pytest

from app.core.config import Settings
from app.core.identity import BotIdentity


def test_identity_tokens_are_selected_independently() -> None:
    settings = Settings(
        bot_token="legacy",
        bot_token_cari="cari-token",
        bot_token_sunna="sunna-token",
        bot_token_cami="cami-token",
        bot_token_chie="chie-token",
    )

    assert settings.token_for(BotIdentity.CARI.value) == "cari-token"
    assert settings.token_for(BotIdentity.SUNNA.value) == "sunna-token"
    assert settings.token_for(BotIdentity.CAMI.value) == "cami-token"
    assert settings.token_for(BotIdentity.CHIE.value) == "chie-token"


def test_unknown_identity_falls_back_to_legacy_token() -> None:
    settings = Settings(bot_token="legacy")
    assert settings.token_for("unknown") == "legacy"


def test_runtime_identity_defaults_to_cari() -> None:
    assert Settings().bot_identity is BotIdentity.CARI


def test_runtime_identity_can_select_each_bot() -> None:
    for identity in BotIdentity:
        assert Settings(bot_identity=identity).bot_identity is identity


@pytest.mark.parametrize("identity", list(BotIdentity))
def test_all_identities_are_declared(identity: BotIdentity) -> None:
    assert identity.value in {"cari", "sunna", "cami", "chie"}
