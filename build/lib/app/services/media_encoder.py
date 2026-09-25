from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import shutil

from app.services.media_manager import CapturePlan


class EncoderKind(str, Enum):
    FFMPEG = "ffmpeg"


class EncoderConfigError(ValueError):
    """Invalid local encoder configuration."""


@dataclass(frozen=True, slots=True)
class VideoEncoding:
    width: int = 1280
    height: int = 720
    frame_rate: int = 30
    bitrate: str = "2500k"
    codec: str = "libx264"
    preset: str = "veryfast"


@dataclass(frozen=True, slots=True)
class AudioEncoding:
    sample_rate: int = 48000
    channels: int = 2
    bitrate: str = "128k"
    codec: str = "aac"


@dataclass(frozen=True, slots=True)
class EncoderProfile:
    """Local encoder configuration; no AI, cloud API, or downloader is involved."""

    executable: str = "ffmpeg"
    video: VideoEncoding = VideoEncoding()
    audio: AudioEncoding = AudioEncoding()
    output: str = ""
    format: str | None = None
    overwrite: bool = False
    extra_args: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EncoderCommand:
    executable: str
    arguments: tuple[str, ...]

    @property
    def argv(self) -> tuple[str, ...]:
        return (self.executable, *self.arguments)


class LocalEncoder:
    """Build deterministic commands for a local FFmpeg executable."""

    def __init__(self, kind: EncoderKind = EncoderKind.FFMPEG) -> None:
        self.kind = kind

    def is_available(self, executable: str = "ffmpeg") -> bool:
        return bool(self.resolve_executable(executable))

    def resolve_executable(self, executable: str) -> str | None:
        if not executable.strip():
            raise EncoderConfigError("encoder executable must not be empty")
        candidate = Path(executable)
        if candidate.is_absolute() or candidate.parent != Path("."):
            return str(candidate) if candidate.is_file() else None
        return shutil.which(executable)

    def build_command(self, plan: CapturePlan, profile: EncoderProfile) -> EncoderCommand:
        if self.kind is not EncoderKind.FFMPEG:
            raise EncoderConfigError(f"unsupported encoder: {self.kind.value}")
        executable = self.resolve_executable(profile.executable)
        if executable is None:
            raise FileNotFoundError(f"No existe el codificador local: {profile.executable}")
        self._validate_profile(profile)
        plan.validate()

        arguments = list(plan.local_input_args())
        arguments.extend(
            (
                "-s",
                f"{profile.video.width}x{profile.video.height}",
                "-c:v",
                profile.video.codec,
                "-preset",
                profile.video.preset,
                "-b:v",
                profile.video.bitrate,
                "-r",
                str(profile.video.frame_rate),
                "-c:a",
                profile.audio.codec,
                "-ar",
                str(profile.audio.sample_rate),
                "-ac",
                str(profile.audio.channels),
                "-b:a",
                profile.audio.bitrate,
            )
        )
        if profile.format:
            arguments.extend(("-f", profile.format))
        elif profile.output.lower().startswith(("rtmp://", "rtmps://")):
            arguments.extend(("-f", "flv"))
        if profile.overwrite:
            arguments.append("-y")
        arguments.extend(profile.extra_args)
        arguments.append(profile.output)
        return EncoderCommand(executable, tuple(arguments))

    @staticmethod
    def _validate_profile(profile: EncoderProfile) -> None:
        if not profile.output.strip():
            raise EncoderConfigError("encoder output must not be empty")
        if profile.video.width < 1 or profile.video.height < 1:
            raise EncoderConfigError("video dimensions must be positive")
        if profile.video.frame_rate < 1 or profile.video.frame_rate > 240:
            raise EncoderConfigError("video frame_rate must be between 1 and 240")
        if profile.audio.sample_rate < 8000:
            raise EncoderConfigError("audio sample_rate must be at least 8000")
        if profile.audio.channels < 1 or profile.audio.channels > 8:
            raise EncoderConfigError("audio channels must be between 1 and 8")
        if not profile.video.codec.strip() or not profile.audio.codec.strip():
            raise EncoderConfigError("audio/video codecs must not be empty")
