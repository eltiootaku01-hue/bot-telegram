from datetime import datetime, timedelta

from app.core.identity import BotIdentity
from app.core.social_activity import SocialActivity, fatigue_map_from_presence
from app.core.social_memory import SocialMemory


def test_social_activity_becomes_active_conversation_when_multiple_humans_are_recent():
    now = datetime(2026, 9, 10, 12, 0)
    activity = SocialActivity(
        chat_id=-100,
        recent_messages=4,
        active_users=2,
        last_human_message_at=now - timedelta(minutes=2),
        observed_at=now,
    )
    snapshot = activity.to_snapshot(SocialMemory())
    assert snapshot.conversation_active
    assert snapshot.recent_messages == 4
    assert snapshot.minutes_since_last_message == 2


def test_social_activity_is_quiet_after_human_window_expires():
    now = datetime(2026, 9, 10, 12, 0)
    activity = SocialActivity(
        chat_id=-100,
        recent_messages=1,
        active_users=1,
        last_human_message_at=now - timedelta(minutes=20),
        observed_at=now,
    )
    snapshot = activity.to_snapshot(SocialMemory())
    assert not snapshot.conversation_active
    assert snapshot.minutes_since_last_message == 20


def test_presence_fatigue_map_is_copied():
    values = {BotIdentity.CARI: 20}
    copied = fatigue_map_from_presence(values)
    assert copied == values
    assert copied is not values
