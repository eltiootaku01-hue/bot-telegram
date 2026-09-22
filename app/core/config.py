import json
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.identity import BotIdentity


class Settings(BaseSettings):
    # Telegram identity tokens. The legacy token remains available as a fallback.
    bot_token: str = ""
    bot_token_cari: str = ""
    bot_token_sunna: str = ""
    bot_token_cami: str = ""
    bot_token_chie: str = ""
    # Optional neutral presenter bot for persistent Game World events.
    bot_token_world: str = ""

    # Optional public Telegram links/usernames for the desktop setup screen.
    bot_link_cari: str = ""
    bot_link_sunna: str = ""
    bot_link_cami: str = ""
    bot_link_chie: str = ""
    bot_link_world: str = ""
    # Optional Telegram sticker file IDs keyed by the authored sticker catalog key.
    telegram_sticker_file_ids_json: str = "{}"

    # One process per configured identity.
    bot_identity: BotIdentity = BotIdentity.CARI
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///./data/bot.db"
    # Canonical owner identity for permissions; ADMIN_USER_ID remains backwards compatible.
    master_telegram_id: int = 0
    master_username: str = ""
    admin_user_id: int = 0
    media_storage_chat_id: int = 0
    publish_page_chat_id: int = 0
    card_assets_dir: str = "data/card_assets"
    card_upload_max_bytes: int = 10 * 1024 * 1024
    base_group_chat_id: int = 0

    # Telegram access is fail-closed: group/supergroup ids must be explicitly authorized.
    authorized_chat_ids: str = ""
    allow_admin_private_chat: bool = True
    allow_user_private_chat: bool = True
    # Optional daily AI world-curation pass; when false, AI remains manual-only.
    ai_curator_auto: bool = False

    # Chie human verification timeout for newly joined members.
    human_verification_timeout_seconds: int = 120
    human_verification_raid_window_seconds: int = 60
    human_verification_raid_threshold: int = 5
    human_verification_raid_timeout_seconds: int = 45

    # World time is explicit for schedules; persistence remains UTC.
    bot_world_timezone: str = "America/Argentina/Buenos_Aires"

    # Telegram Mini App API bridge hosted by Bot Manager.
    tma_api_enabled: bool = True
    tma_api_host: str = "127.0.0.1"
    tma_api_port: int = 8765
    tma_bot_identity: BotIdentity = BotIdentity.SUNNA
    tma_init_data_max_age_seconds: int = 3600
    tma_allowed_origins: str = "https://eltiootaku01-hue.github.io"
    tma_frontend_base_url: str = ""
    tma_premium_ticket_price_stars: int = 10
    tma_starter_pack_price_stars: int = 25

    # Global/per-bot AI gates. Features must check these before invoking any LLM.
    ai_enabled: bool = False
    ai_enabled_cari: bool | None = None
    ai_enabled_sunna: bool | None = None
    ai_enabled_cami: bool | None = None
    ai_enabled_chie: bool | None = None

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

    # Local card vault / command-center boundary.
    vault_api_url: str = "http://127.0.0.1:8765"
    vault_api_token: str = ""
    card_asset_root: str = "data/card_assets"
    card_thumbnail_root: str = "data/card_thumbnails"

    # Optional outbound Meta messaging adapters.
    meta_graph_api_version: str = "v26.0"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    messenger_page_access_token: str = ""
    messenger_page_id: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", case_sensitive=False)

    @field_validator("bot_world_timezone")
    @classmethod
    def validate_world_timezone(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("bot_world_timezone must not be empty")
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown IANA timezone: {value}") from exc
        return value

    @property
    def telegram_sticker_file_ids(self) -> dict[str, str]:
        """Parse optional sticker file IDs; malformed values fail closed."""
        try:
            raw = json.loads(self.telegram_sticker_file_ids_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(raw, dict):
            return {}
        result: dict[str, str] = {}
        for key, value in raw.items():
            if isinstance(key, str) and isinstance(value, str) and key.strip() and value.strip():
                result[key.strip()] = value.strip()
        return result

    @property
    def authorized_chat_ids_set(self) -> frozenset[int]:
        """Parse the explicit group allowlist; malformed entries fail closed."""
        result: set[int] = set()
        for raw_value in self.authorized_chat_ids.split(","):
            value = raw_value.strip()
            if not value:
                continue
            try:
                result.add(int(value))
            except ValueError:
                continue
        return frozenset(result)

    @property
    def master_user_id(self) -> int:
        return self.master_telegram_id or self.admin_user_id

    def is_master(self, user_id: int | None) -> bool:
        return bool(user_id and self.master_user_id and user_id == self.master_user_id)

    def is_chat_allowed(
        self,
        chat_id: int,
        chat_type: str,
        user_id: int | None = None,
    ) -> bool:
        """Return whether this Telegram chat may reach bot application logic."""
        if chat_type == "private":
            admin_allowed = self.allow_admin_private_chat and self.is_master(user_id)
            return self.allow_user_private_chat or admin_allowed
        if chat_type in {"group", "supergroup"}:
            return chat_id in self.authorized_chat_ids_set
        if chat_type == "channel":
            # Channel posts are accepted only from the explicitly configured media vault.
            return chat_id == self.media_storage_chat_id and chat_id != 0
        return False

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

    def ai_for(self, identity: str | BotIdentity) -> bool:
        name = identity.value if isinstance(identity, BotIdentity) else identity.lower()
        override = {
            "cari": self.ai_enabled_cari,
            "sunna": self.ai_enabled_sunna,
            "cami": self.ai_enabled_cami,
            "chie": self.ai_enabled_chie,
        }.get(name)
        return self.ai_enabled if override is None else override


@lru_cache
def get_settings() -> Settings:
    return Settings()
