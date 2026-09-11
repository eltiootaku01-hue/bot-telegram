from datetime import datetime, timedelta

from app.core.social_wake import SocialWakeController, WakeReason


def test_scheduled_wake_stays_in_the_30_to_60_minute_band():
    now = datetime(2026, 9, 10, 12, 0)
    controller = SocialWakeController()

    state = controller.schedule(now, roll=17)

    assert state.next_wake_at == now + timedelta(minutes=47)


def test_event_wake_pulls_a_future_check_forward_and_coalesces():
    now = datetime(2026, 9, 10, 12, 0)
    controller = SocialWakeController()
    state = controller.schedule(now, roll=30)
    later = now + timedelta(minutes=5)

    state = controller.request_wake(state, later)
    again = controller.request_wake(state, later + timedelta(minutes=1))

    assert state.next_wake_at == later
    assert state.pending_reason == WakeReason.EVENT
    assert again == state


def test_busy_chat_stretches_the_next_opportunity():
    now = datetime(2026, 9, 10, 12, 0)
    controller = SocialWakeController()
    state = controller.schedule(now)

    next_state = controller.after_check(state, now, spoke=False, chat_busy=True)

    assert next_state.next_wake_at == now + timedelta(minutes=45)
    assert next_state.consecutive_silences == 1


def test_repeated_silence_progressively_backs_off_without_exceeding_maximum():
    now = datetime(2026, 9, 10, 12, 0)
    controller = SocialWakeController()
    state = controller.schedule(now)

    state = controller.after_check(state, now, spoke=False)
    assert state.next_wake_at == now + timedelta(minutes=35)
    state = controller.after_check(state, now, spoke=False)
    assert state.next_wake_at == now + timedelta(minutes=40)
    state = controller.after_check(state, now, spoke=False)
    assert state.next_wake_at == now + timedelta(minutes=45)


def test_cooldown_prevents_immediate_event_wake_after_a_check():
    now = datetime(2026, 9, 10, 12, 0)
    controller = SocialWakeController()
    state = controller.after_check(controller.schedule(now), now, spoke=True)

    requested = controller.request_wake(state, now + timedelta(minutes=5))

    assert requested == state
    assert not controller.due(requested, now + timedelta(minutes=5))
