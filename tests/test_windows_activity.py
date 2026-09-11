import app.core.windows_activity as windows_activity


def test_non_windows_activity_detector_is_safe(monkeypatch):
    monkeypatch.setattr(windows_activity.os, "name", "posix")
    assert windows_activity.seconds_since_last_input() is None
    assert not windows_activity.pc_is_idle(threshold_seconds=1)


def test_idle_detector_uses_threshold(monkeypatch):
    monkeypatch.setattr(windows_activity, "seconds_since_last_input", lambda: 300.0)
    assert windows_activity.pc_is_idle(threshold_seconds=300)
    assert not windows_activity.pc_is_idle(threshold_seconds=301)
