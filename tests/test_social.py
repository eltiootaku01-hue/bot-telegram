from app.core.identity import BotIdentity
from app.core.social import (
    ACTIVITY_COSTS,
    PERSONALITY_POLICIES,
    choose_followup,
    rank_interveners,
    should_intervene,
)


def test_all_bots_have_distinct_social_personality_policy():
    assert set(PERSONALITY_POLICIES) == set(BotIdentity)
    assert PERSONALITY_POLICIES[BotIdentity.SUNNA].max_reply_sentences == 1
    assert PERSONALITY_POLICIES[BotIdentity.SUNNA].can_finish_another_bot
    assert PERSONALITY_POLICIES[BotIdentity.CARI].can_finish_another_bot
    assert PERSONALITY_POLICIES[BotIdentity.CHIE].can_finish_another_bot
    assert PERSONALITY_POLICIES[BotIdentity.CARI].intervention_weight > PERSONALITY_POLICIES[BotIdentity.SUNNA].intervention_weight


def test_all_bots_have_activity_costs():
    assert set(ACTIVITY_COSTS) == set(BotIdentity)
    assert all(cost.ai_call >= cost.reply for cost in ACTIVITY_COSTS.values())
    assert all(cost.web_lookup >= cost.reply for cost in ACTIVITY_COSTS.values())


def test_busy_chat_is_not_interrupted():
    assert not should_intervene(recent_messages=8, minutes_since_last_message=60)
    assert not should_intervene(recent_messages=12, minutes_since_last_message=120)
    assert rank_interveners(
        recent_messages=10,
        minutes_since_last_message=120,
        fatigue_by_bot={identity: 0 for identity in BotIdentity},
    ) == ()


def test_quiet_chat_can_be_nudged_after_cooldown():
    assert not should_intervene(recent_messages=2, minutes_since_last_message=29)
    assert should_intervene(recent_messages=2, minutes_since_last_message=30)


def test_intervener_selection_prefers_low_fatigue_and_personality_fit():
    ranked = rank_interveners(
        recent_messages=2,
        minutes_since_last_message=35,
        fatigue_by_bot={
            BotIdentity.CARI: 10,
            BotIdentity.SUNNA: 0,
            BotIdentity.CAMI: 10,
            BotIdentity.CHIE: 10,
        },
    )
    assert ranked[0] == BotIdentity.CARI


def test_exhausted_bots_are_excluded_from_social_nudges():
    ranked = rank_interveners(
        recent_messages=1,
        minutes_since_last_message=40,
        fatigue_by_bot={identity: 0 for identity in BotIdentity} | {BotIdentity.CARI: 100},
    )
    assert BotIdentity.CARI not in ranked


def test_sunna_can_have_cari_or_chie_as_delayed_helper():
    helpers = {choose_followup(speaker=BotIdentity.SUNNA, rng_value=value) for value in (0, 1)}
    assert helpers == {BotIdentity.CARI, BotIdentity.CHIE}


def test_followup_can_intentionally_remain_silent():
    assert choose_followup(speaker=BotIdentity.SUNNA, rng_value=-1) is None
