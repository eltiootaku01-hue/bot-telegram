import asyncio
import json
from pathlib import Path

import pytest

from app.core.identity import BotIdentity
from app.multibot.config import MultiBotConfig
from app.multibot.dialogues.manager import DialogueManager
from app.multibot.filters import BotIdentityFilter


def test_multibot_config_accepts_requested_and_legacy_token_names(monkeypatch) -> None:
    values = {
        "CARI_BOT_TOKEN": "1:token",
        "SUNNA_BOT_TOKEN": "2:token",
        "CAMI_BOT_TOKEN": "3:token",
        "CHIE_BOT_TOKEN": "4:token",
        "VAULT_API_URL": "http://127.0.0.1:8765",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    config = MultiBotConfig.from_env()
    assert config.cari_token == "1:token"
    assert config.sunna_token == "2:token"
    assert config.vault_api_url == "http://127.0.0.1:8765"


def test_multibot_filter_is_identity_specific() -> None:
    class FakeBot:
        def __init__(self, bot_id: int) -> None:
            self.id = bot_id

    bot_ids = {
        BotIdentity.CARI: 10,
        BotIdentity.SUNNA: 20,
        BotIdentity.CAMI: 30,
        BotIdentity.CHIE: 40,
    }
    filt = BotIdentityFilter(BotIdentity.SUNNA, bot_ids)

    assert asyncio.run(filt(None, FakeBot(20))) is True
    assert asyncio.run(filt(None, FakeBot(10))) is False


def test_multibot_dialogue_manager_uses_shared_offline_catalog(tmp_path: Path) -> None:
    path = tmp_path / "dialogues.json"
    path.write_text(
        json.dumps({"ON_CARD_ROLL": {"sunna": ["Carta {card_name}"]}}),
        encoding="utf-8",
    )
    manager = DialogueManager(str(path))
    assert (
        manager.render("ON_CARD_ROLL", "sunna", {"card_name": "#001 Rei"})
        == "Carta #001 Rei"
    )


def test_required_handlers_expose_identity_filter_contract() -> None:
    from app.multibot.handlers import cami, cari, chie, sunna

    assert all(
        "identity_filter" in str(builder)
        for builder in (
            sunna.build_router,
            cari.build_router,
            cami.build_router,
            chie.build_router,
        )
    )


def test_validate_bot_ids_rejects_shared_telegram_identity() -> None:
    from app.multibot.main import validate_bot_ids

    with pytest.raises(ValueError, match="same Telegram bot"):
        validate_bot_ids(
            {
                BotIdentity.CARI: 10,
                BotIdentity.SUNNA: 10,
                BotIdentity.CAMI: 30,
                BotIdentity.CHIE: 40,
            }
        )
