from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Legacy single-token mode remains available while the four identities are wired up.
    bot_token: str = ""
    bot_token_cari: str = ""
    bot_token_sunna: str = ""
    bot_token_cami: str = ""
    bot_token_chie: str = ""
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///./data/bot.db"
    admin_user_id: int = 0
    media_storage_chat_id: int = 0
    publish_page_chat_id: int = 0

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", case_sensitive=False)

    def token_for(self, identity: str) -> str:
        token = {
            "cari": self.bot_token_cari,
            "sunna": self.bot_token_sunna,
            "cami": self.bot_token_cami,
            "chie": self.bot_token_chie,
        }.get(identity.lower(), "")
        return token or self.bot_token


@lru_cache
def get_settings() -> Settings:
    return Settings()
