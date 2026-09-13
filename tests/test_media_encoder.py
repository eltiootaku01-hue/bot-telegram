from __future__ import annotations

from pathlib import Path

import pytest

from app.services.media_encoder import AudioEncoding, EncoderConfigError, EncoderProfile, LocalEncoder, VideoEncoding
from app.services.media_manager import CapturePlan, MediaSource, MediaSourceKind


def _fake_ffmpeg(tmp_path: Path) -> str:
    path = tmp_path / ("ffmpeg.exe" if __import__("os").name == "nt" else "ffmpeg")
    path.write_text("test", encoding="utf-8")
    return str(path)


def test_missing_encoder_is_reported() -> None:
    encoder = LocalEncoder()
    with pytest.raises(FileNotFoundError, match="codificador local"):
        encoder.build_command(
            CapturePlan((MediaSource("image", MediaSourceKind.IMAGE, __file__),)),
            EncoderProfile(executable="C:/missing/ffmpeg.exe", output="out.mp4"),
        )


def test_encoder_builds_local_file_command(tmp_path: Path) -> None:
    image = tmp_path / "test.png"
    image.write_bytes(b"x")
    executable = _fake_ffmpeg(tmp_path)
    plan = CapturePlan((MediaSource("image", MediaSourceKind.IMAGE, str(image), 30),))

    command = LocalEncoder().build_command(
        plan,
        EncoderProfile(
            executable=executable,
            video=VideoEncoding(width=1920, height=1080, frame_rate=30, bitrate="4000k"),
            audio=AudioEncoding(sample_rate=48000, channels=2, bitrate="160k"),
            output=str(tmp_path / "capture.mkv"),
        ),
    )

    assert command.executable == executable
    assert "-c:v" in command.arguments
    assert "1920" not in command.arguments
    assert command.arguments[-1].endswith("capture.mkv")


def test_rtmp_output_infers_flv_container(tmp_path: Path) -> None:
    image = tmp_path / "test.png"
    image.write_bytes(b"x")
    executable = _fake_ffmpeg(tmp_path)
    plan = CapturePlan((MediaSource("image", MediaSourceKind.IMAGE, str(image)),))

    command = LocalEncoder().build_command(
        plan,
        EncoderProfile(executable=executable, output="rtmp://example.invalid/live/test"),
    )

    assert "-f" in command.arguments
    index = command.arguments.index("-f")
    assert command.arguments[index + 1] == "flv"


def test_profile_rejects_invalid_dimensions(tmp_path: Path) -> None:
    image = tmp_path / "test.png"
    image.write_bytes(b"x")
    executable = _fake_ffmpeg(tmp_path)
    plan = CapturePlan((MediaSource("image", MediaSourceKind.IMAGE, str(image)),))

    with pytest.raises(EncoderConfigError, match="dimensions"):
        LocalEncoder().build_command(
            plan,
            EncoderProfile(
                executable=executable,
                video=VideoEncoding(width=0, height=720),
                output="capture.mp4",
            ),
        )


def test_capture_plan_reaches_encoder_with_real_microphone_and_screen(tmp_path: Path) -> None:
    image = tmp_path / "test.png"
    image.write_bytes(b"x")
    executable = _fake_ffmpeg(tmp_path)
    plan = CapturePlan(
        (
            MediaSource("screen", MediaSourceKind.SCREEN),
            MediaSource("mic", MediaSourceKind.MICROPHONE, "Microphone Array"),
        )
    )

    command = LocalEncoder().build_command(
        plan,
        EncoderProfile(executable=executable, output=str(tmp_path / "capture.mp4")),
    )

    assert "gdigrab" in command.arguments
    assert "audio=Microphone Array" in command.arguments
