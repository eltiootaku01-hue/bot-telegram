from __future__ import annotations

import sys
import time

import pytest

from app.services.native_media import MediaProfile, MediaSessionState, NativeMediaSession


def test_missing_absolute_executable_fails_without_ai_or_network() -> None:
    session = NativeMediaSession()
    result = session.start(
        MediaProfile(
            name="missing",
            executable="C:/definitely-missing-native-encoder.exe",
            arguments=(),
        )
    )

    assert result.state is MediaSessionState.FAILED
    assert "No existe" in (result.error or "")


def test_local_process_can_start_and_stop() -> None:
    session = NativeMediaSession()
    command = ["-c", "import time; time.sleep(30)"] if sys.platform == "win32" else ["-c", "import time; time.sleep(30)"]
    result = session.start(MediaProfile("test", sys.executable, tuple(command)))

    assert result.state is MediaSessionState.RUNNING
    time.sleep(0.05)
    stopped = session.stop(timeout=1.0)
    assert stopped.state is MediaSessionState.STOPPED


def test_negative_stop_timeout_is_rejected() -> None:
    with pytest.raises(ValueError, match="timeout"):
        NativeMediaSession().stop(-1)
