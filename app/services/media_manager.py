from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from app.services.native_media import MediaProfile, MediaSessionSnapshot, NativeMediaSession
from app.services.process_reader import ProcessOutput


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
