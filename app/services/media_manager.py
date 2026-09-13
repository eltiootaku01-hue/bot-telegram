from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import RLock

from app.services.native_media import MediaProfile, MediaSessionSnapshot, NativeMediaSession
from app.services.process_reader import ProcessOutput


class MediaSourceKind(str, Enum):
    """Real local capture/input types supported by the future scene engine."""

    FILE = "file"
    IMAGE = "image"
    SCREEN = "screen"
    WINDOW = "window"
    WEBCAM = "webcam"
    MICROPHONE = "microphone"


@dataclass(frozen=True, slots=True)
class MediaSource:
    """Deterministic description of one real local source.

    This object never contacts an AI service or cloud API. A local encoder
    consumes the generated arguments when it is available on the Windows PC.
    """

    id: str
    kind: MediaSourceKind
    value: str = ""
    frame_rate: int = 30

    def validate(self) -> None:
        if not self.id.strip():
            raise ValueError("source id must not be empty")
        if self.frame_rate < 1 or self.frame_rate > 240:
            raise ValueError("frame_rate must be between 1 and 240")
        if self.kind in {MediaSourceKind.FILE, MediaSourceKind.IMAGE}:
            if not self.value.strip():
                raise ValueError("a local media path is required")
            if not Path(self.value).is_file():
                raise FileNotFoundError(f"No existe el archivo multimedia local: {self.value}")
        elif self.kind in {
            MediaSourceKind.WINDOW,
            MediaSourceKind.WEBCAM,
            MediaSourceKind.MICROPHONE,
        } and not self.value.strip():
            raise ValueError(f"a device/window name is required for {self.kind.value}")

    def local_input_args(self) -> tuple[str, ...]:
        """Return deterministic Windows capture arguments for a local encoder."""
        self.validate()
        if self.kind is MediaSourceKind.FILE:
            return ("-re", "-i", self.value)
        if self.kind is MediaSourceKind.IMAGE:
            return ("-loop", "1", "-framerate", str(self.frame_rate), "-i", self.value)
        if self.kind is MediaSourceKind.SCREEN:
            return ("-f", "gdigrab", "-framerate", str(self.frame_rate), "-i", "desktop")
        if self.kind is MediaSourceKind.WINDOW:
            return (
                "-f",
                "gdigrab",
                "-framerate",
                str(self.frame_rate),
                "-i",
                f"title={self.value}",
            )
        if self.kind is MediaSourceKind.WEBCAM:
            return (
                "-f",
                "dshow",
                "-framerate",
                str(self.frame_rate),
                "-i",
                f"video={self.value}",
            )
        return ("-f", "dshow", "-i", f"audio={self.value}")


@dataclass(frozen=True, slots=True)
class CapturePlan:
    """Validate and preserve an ordered set of real local sources."""

    sources: tuple[MediaSource, ...]

    def validate(self) -> None:
        ids: set[str] = set()
        for source in self.sources:
            source.validate()
            if source.id in ids:
                raise ValueError(f"duplicate media source: {source.id}")
            ids.add(source.id)

    def local_input_args(self) -> tuple[str, ...]:
        self.validate()
        result: list[str] = []
        for source in self.sources:
            result.extend(source.local_input_args())
        return tuple(result)


@dataclass(frozen=True, slots=True)
class MediaOutput:
    """Named local output managed by the Windows application."""

    id: str
    profile: MediaProfile


class MediaManager:
    """Manage multiple independent local media outputs without AI or APIs."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._outputs: dict[str, MediaOutput] = {}
        self._sessions: dict[str, NativeMediaSession] = {}

    def register(self, output: MediaOutput) -> None:
        if not output.id.strip():
            raise ValueError("output id must not be empty")
        with self._lock:
            if output.id in self._outputs:
                raise ValueError(f"duplicate media output: {output.id}")
            self._outputs[output.id] = output
            self._sessions[output.id] = NativeMediaSession()

    def get(self, output_id: str) -> MediaOutput | None:
        with self._lock:
            return self._outputs.get(output_id)

    def start(self, output_id: str) -> MediaSessionSnapshot:
        output = self._require(output_id)
        return self._sessions[output_id].start(output.profile)

    def start_encoded(self, output_id: str, plan: CapturePlan, profile) -> MediaSessionSnapshot:
        """Start an output using the local encoder command generated from sources."""
        self._require(output_id)
        from app.services.media_encoder import LocalEncoder

        command = LocalEncoder().build_command(plan, profile)
        media_profile = MediaProfile(output_id, command.executable, command.arguments)
        return self._sessions[output_id].start(media_profile)

    def stop(self, output_id: str, timeout: float = 2.0) -> MediaSessionSnapshot:
        self._require(output_id)
        return self._sessions[output_id].stop(timeout)

    def snapshot(self, output_id: str) -> MediaSessionSnapshot:
        self._require(output_id)
        return self._sessions[output_id].snapshot()

    def drain_output(self, output_id: str) -> list[ProcessOutput]:
        self._require(output_id)
        return self._sessions[output_id].drain_output()

    def stop_all(self, timeout: float = 2.0) -> None:
        with self._lock:
            ids = tuple(self._sessions)
        for output_id in ids:
            self.stop(output_id, timeout)

    def _require(self, output_id: str) -> MediaOutput:
        with self._lock:
            output = self._outputs.get(output_id)
        if output is None:
            raise KeyError(f"unknown media output: {output_id}")
        return output
