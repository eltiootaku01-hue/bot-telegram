from __future__ import annotations

import sys

import pytest

from app.services.media_manager import MediaManager, MediaOutput
from app.services.native_media import MediaProfile, MediaSessionState


def _output(output_id: str = "local") -> MediaOutput:
    return MediaOutput(
        output_id,
        MediaProfile("local-test", sys.executable, ("-c", "import time; time.sleep(30)")),
    )


def test_register_rejects_duplicate_output() -> None:
    manager = MediaManager()
    manager.register(_output())
    with pytest.raises(ValueError, match="duplicate"):
        manager.register(_output())


def test_unknown_output_is_rejected() -> None:
    with pytest.raises(KeyError, match="unknown media output"):
        MediaManager().snapshot("missing")


def test_output_can_start_and_stop() -> None:
    manager = MediaManager()
    manager.register(_output())
    assert manager.start("local").state is MediaSessionState.RUNNING
    assert manager.stop("local", timeout=1).state is MediaSessionState.STOPPED
