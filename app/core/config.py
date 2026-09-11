from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.identity import BotIdentity


class Settings(BaseSettings):
    # Telegram identity tokens. The legacy token remains available as a fallback.
    bot_token: str = ""
    bot_token_cari: str = ""
    bot_token_sunna: str = ""
    bot_token_cami: str = ""
    bot_token_chie: str = ""

    # Optional public Telegram links/usernames for the desktop setup screen.
    bot_link_cari: str = ""
    bot_link_sunna: str = ""
    bot_link_cami: str = ""
    bot_link_chie: str = ""

    # One process per configured identity.
    bot_identity: BotIdentity = BotIdentity.CARI
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///./data/bot.db"
    admin_user_id: int = 0
    media_storage_chat_id: int = 0
    publish_page_chat_id: int = 0

    # AI provider settings are optional until the Brain actually needs an LLM.
    llm_provider: str = ""
    llm_model: str = ""
    llm_base_url: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    cerebras_api_key: str = ""
    openrouter_api_key: str = ""

    # Ollama is local-only and needs no API key. The model can be changed per machine.
    ollama_model: str = "llama3.2:1b"
    ollama_base_url: str = "http://127.0.0.1:11434"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", case_sensitive=False)

    def token_for(self, identity: str) -> str:
        token = {
            "cari": self.bot_token_cari,
            "sunna": self.bot_token_sunna,
            "cami": self.bot_token_cami,
            "chie": self.bot_token_chie,
        }.get(identity.lower(), "")
        return token or self.bot_token

    def link_for(self, identity: str) -> str:
        return {
            "cari": self.bot_link_cari,
            "sunna": self.bot_link_sunna,
            "cami": self.bot_link_cami,
            "chie": self.bot_link_chie,
        }.get(identity.lower(), "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
