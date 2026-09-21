from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.time import utc_now


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(255), default="")
    last_name: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(16))
    is_bot: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Chat(Base):
    __tablename__ = "chats"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[str] = mapped_column(String(32), default="unknown")
    title: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_human_message_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_bot_message_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_social_event_at: Mapped[datetime | None] = mapped_column(DateTime)


class UserChat(Base):
    __tablename__ = "user_chats"
    __table_args__ = (UniqueConstraint("user_id", "chat_id", name="uq_user_chat"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32), default="member")
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime)
    left_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)



class HumanVerification(Base):
    """Durable human-verification state for community membership."""
    __tablename__ = "human_verifications"
    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_human_verification_chat_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    prompt_message_id: Mapped[int | None] = mapped_column(BigInteger)
    default_permissions_json: Mapped[str] = mapped_column(String(4000), default="{}")
    prompted_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ModerationAction(Base):
    """Auditable explicit moderation action issued by a Telegram administrator."""

    __tablename__ = "moderation_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    target_user_id: Mapped[int] = mapped_column(BigInteger)
    moderator_user_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(1000), default="")
    until_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)





class StoryProgress(Base):
    """Durable position in the authored runtime story for one community."""

    __tablename__ = "story_progress"
    __table_args__ = (
        UniqueConstraint("chat_id", "arc_key", name="uq_story_progress_chat_arc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    arc_key: Mapped[str] = mapped_column(String(64))
    chapter: Mapped[int] = mapped_column(Integer, default=1)
    completed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GameProfile(Base):
    __tablename__ = "game_profiles"
    __table_args__ = (UniqueConstraint("user_id", "chat_id", name="uq_game_profile"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    level: Mapped[int] = mapped_column(Integer, default=1)
    experience: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[int] = mapped_column(Integer, default=0)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    gacha_d_streak: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class PointTransaction(Base):
    __tablename__ = "point_transactions"
    __table_args__ = (UniqueConstraint("user_id", "chat_id", "reference_type", "reference_id", name="uq_point_transaction_reference"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(255))
    reference_type: Mapped[str | None] = mapped_column(String(64))
    reference_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GameCollection(Base):
    __tablename__ = "game_collection"
    __table_args__ = (UniqueConstraint("profile_id", "character_id", name="uq_collection_character"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("game_profiles.id", ondelete="CASCADE"))
    character_id: Mapped[str] = mapped_column(String(100))
    rarity: Mapped[str] = mapped_column(String(32))
    level: Mapped[int] = mapped_column(Integer, default=1)
    copies: Mapped[int] = mapped_column(Integer, default=1)
    experience: Mapped[int] = mapped_column(Integer, default=0)
    evolution_stage: Mapped[int] = mapped_column(Integer, default=1)
    obtained_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GameEncounter(Base):
    __tablename__ = "game_encounters"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    character_id: Mapped[str] = mapped_column(String(100))
    rarity: Mapped[str] = mapped_column(String(32))
    question: Mapped[str | None] = mapped_column(String(1000))
    answer: Mapped[str | None] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32), default="active")


class GameAttempt(Base):
    __tablename__ = "game_attempts"
    __table_args__ = (UniqueConstraint("encounter_id", "user_id", name="uq_encounter_attempt"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    encounter_id: Mapped[str] = mapped_column(ForeignKey("game_encounters.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger)
    answer: Mapped[str] = mapped_column(String(500))
    correct: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class RareDropApproval(Base):
    __tablename__ = "rare_drop_approvals"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    character_id: Mapped[str] = mapped_column(String(100))
    rarity: Mapped[str] = mapped_column(String(32))
    target_user_id: Mapped[int] = mapped_column(BigInteger)
    target_chat_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)


class GameItemInventory(Base):
    """Items received from Sunna and stored for later waifu absorption."""

    __tablename__ = "game_item_inventory"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "item_key",
            name="uq_game_item_inventory_profile_item",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("game_profiles.id", ondelete="CASCADE"))
    item_key: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class WaifuGiftDrop(Base):
    """A community gift drop that can be claimed by at most three users."""

    __tablename__ = "waifu_gift_drops"
    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "day_key",
            "slot",
            name="uq_waifu_gift_drop_chat_day_slot",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    day_key: Mapped[str] = mapped_column(String(16))
    slot: Mapped[int] = mapped_column(Integer)
    gift_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class WaifuGiftClaim(Base):
    """One claim per user for one community gift drop."""

    __tablename__ = "waifu_gift_claims"
    __table_args__ = (
        UniqueConstraint(
            "drop_id",
            "user_id",
            name="uq_waifu_gift_claim_drop_user",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    drop_id: Mapped[int] = mapped_column(ForeignKey("waifu_gift_drops.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class WaifuDetectorDailyUsage(Base):
    """Daily counter limiting each player to three Waifu Detector fights."""

    __tablename__ = "waifu_detector_daily_usage"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "chat_id",
            "day_key",
            name="uq_detector_daily_usage_user_chat_day",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    day_key: Mapped[str] = mapped_column(String(16))
    uses: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class WaifuDetectorRound(Base):
    """One irreversible mob fight allocated to one player."""

    __tablename__ = "waifu_detector_rounds"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "chat_id",
            "day_key",
            "use_number",
            name="uq_detector_round_user_chat_day_use",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    day_key: Mapped[str] = mapped_column(String(16))
    use_number: Mapped[int] = mapped_column(Integer)
    character_id: Mapped[str] = mapped_column(String(100))
    mob_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="active")
    result: Mapped[str] = mapped_column(String(32), default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GameCardCollection(Base):
    """Collectible card inventory; separate from character progression."""
    __tablename__ = "game_card_collections"
    __table_args__ = (
        UniqueConstraint("profile_id", "card_id", name="uq_game_card_profile_card"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("game_profiles.id", ondelete="CASCADE"))
    card_id: Mapped[str] = mapped_column(String(255))
    character_id: Mapped[str] = mapped_column(String(100))
    card_tier: Mapped[str] = mapped_column(String(8))
    variant: Mapped[str] = mapped_column(String(16))
    outfit: Mapped[str] = mapped_column(String(64))
    fusion_of_a: Mapped[str | None] = mapped_column(String(100))
    fusion_of_b: Mapped[str | None] = mapped_column(String(100))
    copies: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GameGachaRoll(Base):
    """Durable ledger for one gacha roll, preventing duplicate rewards."""

    __tablename__ = "game_gacha_rolls"
    __table_args__ = (
        UniqueConstraint("roll_id", name="uq_game_gacha_roll_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    roll_id: Mapped[str] = mapped_column(String(255))
    user_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    rolled_rarity: Mapped[str] = mapped_column(String(32))
    character_id: Mapped[str] = mapped_column(String(100))
    approval_id: Mapped[int | None] = mapped_column(ForeignKey("rare_drop_approvals.id", ondelete="SET NULL"))
    granted: Mapped[bool] = mapped_column(default=False)
    pity_triggered: Mapped[bool] = mapped_column(default=False)
    card_id: Mapped[str | None] = mapped_column(String(255))
    card_variant: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GameDailyMissionProgress(Base):
    """Durable progress for one player's daily mission in one community."""

    __tablename__ = "game_daily_mission_progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "chat_id",
            "day_key",
            "mission_key",
            name="uq_game_daily_mission_progress",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    day_key: Mapped[str] = mapped_column(String(16))
    mission_key: Mapped[str] = mapped_column(String(64))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    target: Mapped[int] = mapped_column(Integer)
    claimed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GameDailyMissionCredit(Base):
    """Unique source credit proving one gameplay action counted once."""

    __tablename__ = "game_daily_mission_credits"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "chat_id",
            "day_key",
            "mission_key",
            "reference_type",
            "reference_id",
            name="uq_game_daily_mission_credit",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    day_key: Mapped[str] = mapped_column(String(16))
    mission_key: Mapped[str] = mapped_column(String(64))
    reference_type: Mapped[str] = mapped_column(String(64))
    reference_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class MediaAlbum(Base):
    """Durable identity for one Telegram media group handled as an operator unit."""

    __tablename__ = "media_albums"
    __table_args__ = (
        UniqueConstraint("source_chat_id", "media_group_id", name="uq_media_album_source_group"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_chat_id: Mapped[int] = mapped_column(BigInteger)
    media_group_id: Mapped[str] = mapped_column(String(128))
    owner_user_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32), default="open")
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    prompted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class MediaAsset(Base):
    __tablename__ = "media_assets"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_file_id: Mapped[str] = mapped_column(String(512), unique=True)
    telegram_unique_id: Mapped[str | None] = mapped_column(String(255))
    source_chat_id: Mapped[int] = mapped_column(BigInteger)
    source_message_id: Mapped[int] = mapped_column(BigInteger)
    media_group_id: Mapped[str | None] = mapped_column(String(128))
    media_type: Mapped[str] = mapped_column(String(32), default="photo")
    request_id: Mapped[int | None] = mapped_column(ForeignKey("fan_requests.id", ondelete="SET NULL"))
    character_id: Mapped[str | None] = mapped_column(String(100))
    anime: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[str] = mapped_column(String(2000), default="")
    category: Mapped[str | None] = mapped_column(String(64))
    rarity: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="inbox")
    publish_group: Mapped[bool] = mapped_column(default=False)
    publish_page: Mapped[bool] = mapped_column(default=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    publish_destination: Mapped[str | None] = mapped_column(String(32))
    publish_group_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    published_group_message_id: Mapped[int | None] = mapped_column(BigInteger)
    published_page_message_id: Mapped[int | None] = mapped_column(BigInteger)
    published_request_message_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class CafeDailyEventRound(Base):
    """One authored non-canonical daily Café Otaku world event per community."""

    __tablename__ = "cafe_daily_event_rounds"
    __table_args__ = (
        UniqueConstraint("chat_id", "day_key", name="uq_cafe_daily_event_chat_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    day_key: Mapped[str] = mapped_column(String(16))
    event_key: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(32), default="active")
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class MysteryRound(Base):
    """Daily Café Otaku mystery, one deterministic case per community/day."""

    __tablename__ = "mystery_rounds"
    __table_args__ = (
        UniqueConstraint("chat_id", "day_key", name="uq_mystery_round_chat_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    day_key: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(255))
    question: Mapped[str] = mapped_column(String(1000))
    clues_json: Mapped[str] = mapped_column(String(4000), default="[]")
    options_json: Mapped[str] = mapped_column(String(2000), default="[]")
    answer_index: Mapped[int] = mapped_column(Integer)
    points: Mapped[int] = mapped_column(Integer, default=15)
    status: Mapped[str] = mapped_column(String(32), default="active")
    winner_user_id: Mapped[int | None] = mapped_column(BigInteger)
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class MysteryAttempt(Base):
    """One answer attempt per player and mystery round."""

    __tablename__ = "mystery_attempts"
    __table_args__ = (
        UniqueConstraint("round_id", "user_id", name="uq_mystery_attempt"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("mystery_rounds.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger)
    option_index: Mapped[int] = mapped_column(Integer)
    correct: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class GameCharacterArt(Base):
    __tablename__ = "game_character_art"
    __table_args__ = (UniqueConstraint("character_id", "evolution_stage", name="uq_character_art_stage"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    character_id: Mapped[str] = mapped_column(String(100))
    evolution_stage: Mapped[int] = mapped_column(Integer, default=1)
    asset_id: Mapped[int] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"))
    is_primary: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class RequestStatus(StrEnum):
    NEW = "new"
    NEEDS_INFO = "needs_info"
    PENDING_ADMIN = "pending_admin"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class FanRequest(Base):
    __tablename__ = "fan_requests"
    __table_args__ = (UniqueConstraint("user_id", "chat_id", "source_message_id", name="uq_fan_request_source"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(String(4000))
    character_id: Mapped[str | None] = mapped_column(String(100))
    special_details: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(32), default=RequestStatus.NEW.value)
    points_cost: Mapped[int] = mapped_column(Integer, default=0)
    source_message_id: Mapped[int | None] = mapped_column(BigInteger)
    admin_note: Mapped[str | None] = mapped_column(String(4000))
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AnimeWork(Base):
    """Locally curated anime/manga work metadata with explicit provenance."""

    __tablename__ = "anime_works"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    titles_json: Mapped[str] = mapped_column(String(4000), default="[]")
    media_type: Mapped[str] = mapped_column(String(32), default="unknown")
    status: Mapped[str] = mapped_column(String(64), default="unverified")
    year_start: Mapped[int | None] = mapped_column(Integer)
    year_end: Mapped[int | None] = mapped_column(Integer)
    episodes: Mapped[int | None] = mapped_column(Integer)
    genres_json: Mapped[str] = mapped_column(String(4000), default="[]")
    themes_json: Mapped[str] = mapped_column(String(4000), default="[]")
    studio: Mapped[str | None] = mapped_column(String(255))
    source_ids_json: Mapped[str] = mapped_column(String(4000), default="{}")
    source_urls_json: Mapped[str] = mapped_column(String(8000), default="[]")
    summary_short: Mapped[str] = mapped_column(String(4000), default="")
    notes_json: Mapped[str] = mapped_column(String(4000), default="[]")
    last_verified: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AnimeCharacter(Base):
    """Locally curated character metadata linked to one canonical work record."""

    __tablename__ = "anime_characters"
    __table_args__ = (
        UniqueConstraint("work_id", "name", name="uq_anime_character_work_name"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    work_id: Mapped[str] = mapped_column(ForeignKey("anime_works.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    aliases_json: Mapped[str] = mapped_column(String(4000), default="[]")
    source_ids_json: Mapped[str] = mapped_column(String(4000), default="{}")
    source_urls_json: Mapped[str] = mapped_column(String(8000), default="[]")
    notes: Mapped[str] = mapped_column(String(4000), default="")
    last_verified: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class BotSetting(Base):
    __tablename__ = "bot_settings"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int | None] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(String(4000), default="")


class BotPresence(StrEnum):
    ACTIVE = "active"
    RESTING = "resting"
    MANUAL_OFF = "manual_off"


class BotPresenceState(Base):
    __tablename__ = "bot_presence_states"
    __table_args__ = (UniqueConstraint("bot_identity", name="uq_bot_presence_identity"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bot_identity: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default=BotPresence.ACTIVE.value)
    energy: Mapped[int] = mapped_column(Integer, default=0)
    rest_until: Mapped[datetime | None] = mapped_column(DateTime)
    auto_resume: Mapped[bool] = mapped_column(default=True)
    pc_idle_required: Mapped[bool] = mapped_column(default=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DomainEvent(Base):
    __tablename__ = "domain_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_domain_event_id"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[str] = mapped_column(String(10000), default="{}")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DurableJob(Base):
    __tablename__ = "durable_jobs"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_durable_job_dedupe"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(100))
    dedupe_key: Mapped[str] = mapped_column(String(255))
    payload: Mapped[str] = mapped_column(String(10000), default="{}")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    run_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class TioOperatorRequest(Base):
    """Human-operated inbox item for messages explicitly addressed to Tío Otaku."""

    __tablename__ = "tio_operator_requests"
    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "source_message_id",
            name="uq_tio_operator_request_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    source_message_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(String(4000))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
