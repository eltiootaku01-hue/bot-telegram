from datetime import datetime, timedelta

from app.core.identity import BotIdentity
from app.core.social_memory import SocialMemory, SocialObservation, human_activity_dominates, should_arm_followup


def test_human_activity_can_suppress_bot_initiative():
    now = datetime(2026, 9, 10, 12, 0)
    observation = SocialObservation(
        chat_id=1,
        message_count=12,
        active_users=3,
        last_message_at=now - timedelta(minutes=1),
        last_human_message_at=now - timedelta(minutes=2),
        last_bot_message_at=now - timedelta(minutes=50),
        last_event_at=now - timedelta(hours=2),
        observed_at=now,
    )
    assert human_activity_dominates(observation)


def test_one_active_user_does_not_count_as_human_conversation():
    now = datetime(2026, 9, 10, 12, 0)
    observation = SocialObservation(
        chat_id=1,
        message_count=2,
        active_users=1,
        last_message_at=now - timedelta(minutes=1),
        last_human_message_at=now - timedelta(minutes=1),
        last_bot_message_at=None,
        last_event_at=None,
        observed_at=now,
    )
    assert not human_activity_dominates(observation)


def test_followup_is_optional_even_after_sunna():
    assert should_arm_followup(speaker=BotIdentity.SUNNA, now=datetime(2026, 9, 10, 12, 0), probability_roll=0)
    assert not should_arm_followup(speaker=BotIdentity.SUNNA, now=datetime(2026, 9, 10, 12, 0), probability_roll=1)
    assert not should_arm_followup(speaker=BotIdentity.SUNNA, now=datetime(2026, 9, 10, 12, 0), probability_roll=-1)


def test_social_memory_clears_followup_after_new_bot_message():
    now = datetime(2026, 9, 10, 12, 0)
    memory = SocialMemory().arm_followup(BotIdentity.CARI, now + timedelta(minutes=5))
    assert memory.followup_due(now + timedelta(minutes=5))
    updated = memory.with_bot_message(BotIdentity.CARI, now + timedelta(minutes=6))
    assert updated.pending_followup_bot is None
    assert updated.last_speaker == BotIdentity.CARI
