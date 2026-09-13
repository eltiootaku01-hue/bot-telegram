from __future__ import annotations

import sys

import pytest

from app.services.media_encoder import EncoderCommand
from app.services.media_manager import CapturePlan, MediaManager, MediaOutput, MediaSource, MediaSourceKind
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


def test_start_encoded_uses_generated_local_encoder_command(monkeypatch, tmp_path) -> None:
    manager = MediaManager()
    manager.register(_output())
    executable = tmp_path / "fake-encoder"
    executable.write_text("test", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_build(self, plan, profile):
        captured["plan"] = plan
        captured["profile"] = profile
        return EncoderCommand(str(executable), ("-test", "output"))

    monkeypatch.setattr("app.services.media_encoder.LocalEncoder.build_command", fake_build)
    session = manager._sessions["local"]
    monkeypatch.setattr(
        session,
        "start",
        lambda profile: captured.update(media_profile=profile)
        or type("Result", (), {"state": MediaSessionState.RUNNING})(),
    )

    source = MediaSource("screen", MediaSourceKind.SCREEN)
    result = manager.start_encoded("local", CapturePlan((source,)), object())

    assert result.state is MediaSessionState.RUNNING
    media_profile = captured["media_profile"]
    assert media_profile.executable == str(executable)
    assert media_profile.arguments == ("-test", "output")
