from app.core.identity import BotIdentity
from app.core.social import (
    ACTIVITY_COSTS,
    PERSONALITY_POLICIES,
    should_intervene,
)


def test_all_bots_have_distinct_social_personality_policy():
    assert set(PERSONALITY_POLICIES) == set(BotIdentity)
    assert PERSONALITY_POLICIES[BotIdentity.SUNNA].max_reply_sentences == 1
    assert PERSONALITY_POLICIES[BotIdentity.SUNNA].can_finish_another_bot
    assert PERSONALITY_POLICIES[BotIdentity.CARI].intervention_weight > PERSONALITY_POLICIES[BotIdentity.SUNNA].intervention_weight


def test_all_bots_have_activity_costs():
    assert set(ACTIVITY_COSTS) == set(BotIdentity)
    assert all(cost.ai_call >= cost.reply for cost in ACTIVITY_COSTS.values())
    assert all(cost.web_lookup >= cost.reply for cost in ACTIVITY_COSTS.values())


def test_busy_chat_is_not_interrupted():
    assert not should_intervene(recent_messages=8, minutes_since_last_message=60)
    assert not should_intervene(recent_messages=12, minutes_since_last_message=120)


def test_quiet_chat_can_be_nudged_after_cooldown():
    assert not should_intervene(recent_messages=2, minutes_since_last_message=29)
    assert should_intervene(recent_messages=2, minutes_since_last_message=30)
