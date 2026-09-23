from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv

from app.core.identity import BotIdentity


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


@dataclass(frozen=True, slots=True)
class MultiBotConfig:
    cari_token: str
    sunna_token: str
    cami_token: str
    chie_token: str
    vault_api_url: str = "http://127.0.0.1:8766"
    vault_api_token: str = ""
    default_bank_key: str = "main-bank"

    @classmethod
    def from_env(cls) -> "MultiBotConfig":
        load_dotenv()
        values = cls(
            cari_token=_first_env("CARI_BOT_TOKEN", "BOT_TOKEN_CARI"),
            sunna_token=_first_env("SUNNA_BOT_TOKEN", "BOT_TOKEN_SUNNA"),
            cami_token=_first_env("CAMI_BOT_TOKEN", "BOT_TOKEN_CAMI"),
            chie_token=_first_env("CHIE_BOT_TOKEN", "BOT_TOKEN_CHIE"),
            vault_api_url=_first_env("VAULT_API_URL") or "http://127.0.0.1:8766",
            vault_api_token=os.getenv("VAULT_API_TOKEN", "").strip(),
            default_bank_key=os.getenv("VAULT_BANK_KEY", "main-bank").strip() or "main-bank",
        )
        values.validate()
        return values

    def validate(self) -> None:
        missing = [
            identity.value
            for identity, token in self.tokens().items()
            if not token
        ]
        if missing:
            raise ValueError("Missing bot token(s): " + ", ".join(missing))
        parsed = urlparse(self.vault_api_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("VAULT_API_URL must be an absolute HTTP(S) URL")

    def tokens(self) -> dict[BotIdentity, str]:
        return {
            BotIdentity.CARI: self.cari_token,
            BotIdentity.SUNNA: self.sunna_token,
            BotIdentity.CAMI: self.cami_token,
            BotIdentity.CHIE: self.chie_token,
        }
