"""Single source of truth for Telegram Forum Topic routing."""

from enum import Enum, IntEnum
from typing import Optional


class ForumTopic(IntEnum):
    """Centralized and immutable Telegram Forum Topic identifiers."""

    ANIME_RELEASES = 1024
    MEME_WALL = 2048
    WEB_COMMENTS = 3072
    POKER_TABLE = 4096
    GACHA_ZONE = 5096
    SECURITY_LOGS = 6096


class WebEventType(str, Enum):
    ANIME_RELEASE = "ANIME_RELEASE"
    MEME_POST = "MEME_POST"
    WEB_COMMENT = "WEB_COMMENT"


EVENT_TO_TOPIC_MAP: dict[WebEventType, ForumTopic] = {
    WebEventType.ANIME_RELEASE: ForumTopic.ANIME_RELEASES,
    WebEventType.MEME_POST: ForumTopic.MEME_WALL,
    WebEventType.WEB_COMMENT: ForumTopic.WEB_COMMENTS,
}


def resolve_topic_for_event(event_type: str) -> Optional[ForumTopic]:
    """Resolve an external event into its canonical Telegram topic."""
    try:
        return EVENT_TO_TOPIC_MAP.get(WebEventType(event_type))
    except ValueError:
        return None
