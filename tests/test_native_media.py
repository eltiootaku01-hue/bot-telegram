from __future__ import annotations

import sys
import time

import pytest

from app.services.native_media import MediaProfile, MediaSessionState, NativeMediaSession


def _profile(code: str) -> MediaProfile:
    return MediaProfile("native-test", sys.executable, ("-c", code))


def test_missing_absolute_executable_fails_without_ai_or_network() -> None:
    session = NativeMediaSession()
    result = session.start(
        MediaProfile("missing", "C:/definitely-missing-native-encoder.exe", ())
    )

    assert result.state is MediaSessionState.FAILED
    assert "No existe" in (result.error or "")


def test_local_process_can_start_and_stop() -> None:
    session = NativeMediaSession()
    result = session.start(_profile("import time; time.sleep(30)"))

    assert result.state is MediaSessionState.RUNNING
    stopped = session.stop(timeout=1.0)
    assert stopped.state is MediaSessionState.STOPPED


def test_negative_stop_timeout_is_rejected() -> None:
    with pytest.raises(ValueError, match="timeout"):
        NativeMediaSession().stop(-1)


def test_early_exit_reports_failure_and_captures_output() -> None:
    session = NativeMediaSession()
    result = session.start(_profile("import sys; print('media-error', flush=True); sys.exit(7)"))
    assert result.state in {MediaSessionState.RUNNING, MediaSessionState.FAILED}

    snapshot = result
    for _ in range(100):
        snapshot = session.snapshot()
        if snapshot.state is not MediaSessionState.RUNNING:
            break
        time.sleep(0.01)

    assert snapshot.state is MediaSessionState.FAILED
    assert snapshot.returncode == 7
    assert "7" in (snapshot.error or "")
    assert any(event.line == "media-error" for event in session.drain_output())


def test_successful_process_finishes_cleanly() -> None:
    session = NativeMediaSession()
    result = session.start(_profile("print('media-ok', flush=True)"))
    assert result.state is MediaSessionState.RUNNING

    snapshot = result
    for _ in range(100):
        snapshot = session.snapshot()
        if snapshot.state is not MediaSessionState.RUNNING:
            break
        time.sleep(0.01)

    assert snapshot.state is MediaSessionState.STOPPED
    assert snapshot.returncode == 0
    assert any(event.line == "media-ok" for event in session.drain_output())
