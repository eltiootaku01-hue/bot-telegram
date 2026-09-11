from datetime import datetime, timedelta

from app.core.identity import BotIdentity
from app.core.social_director import SocialDirector, SocialSnapshot


def snapshot(**overrides):
    values = {
        "recent_messages": 0,
        "active_users": 0,
        "minutes_since_last_message": 40,
        "minutes_since_last_bot_message": 40,
        "minutes_since_last_event": 40,
        "conversation_active": False,
    }
    values.update(overrides)
    return SocialSnapshot(**values)


def test_busy_human_conversation_wins_over_event_schedule():
    decision = SocialDirector().decide(
        snapshot(recent_messages=20, active_users=5, conversation_active=True),
        {identity: 0 for identity in BotIdentity},
    )
    assert not decision.should_speak
    assert decision.reason == "human_conversation_active"


def test_active_chat_is_not_interrupted():
    decision = SocialDirector().decide(
        snapshot(recent_messages=9, active_users=2),
        {identity: 0 for identity in BotIdentity},
    )
    assert not decision.should_speak
    assert decision.reason == "chat_busy"


def test_bot_events_are_spaced_apart():
    decision = SocialDirector().decide(
        snapshot(minutes_since_last_bot_message=10),
        {identity: 0 for identity in BotIdentity},
    )
    assert not decision.should_speak
    assert decision.reason == "bot_cooldown"


def test_quiet_window_returns_candidates_without_forcing_one():
    decision = SocialDirector().decide(
        snapshot(minutes_since_last_message=45),
        {identity: 0 for identity in BotIdentity},
    )
    assert decision.should_speak
    assert decision.candidates
    assert decision.reason == "quiet_window"


def test_all_bots_exhausted_means_silence():
    decision = SocialDirector().decide(
        snapshot(),
        {identity: 100 for identity in BotIdentity},
    )
    assert not decision.should_speak
    assert decision.reason == "no_rested_bot"


def test_followup_requires_a_real_delay():
    now = datetime(2026, 9, 10, 12, 0)
    assert not SocialDirector.followup_allowed(original_bot=BotIdentity.SUNNA, now=now, last_bot_message_at=now - timedelta(minutes=4))
    assert SocialDirector.followup_allowed(original_bot=BotIdentity.SUNNA, now=now, last_bot_message_at=now - timedelta(minutes=5))
