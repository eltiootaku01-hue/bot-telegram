from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
from subprocess import PIPE, Popen, TimeoutExpired
from threading import RLock
from typing import Sequence


class MediaSessionState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class MediaProfile:
    """Local media output definition; no AI or cloud API is involved."""

    name: str
    executable: str
    arguments: tuple[str, ...]
    working_directory: str | None = None


@dataclass(frozen=True, slots=True)
class MediaSessionSnapshot:
    state: MediaSessionState
    returncode: int | None = None
    error: str | None = None


class NativeMediaSession:
    """Own one local media/streaming subprocess on Windows or another OS.

    The manager does not depend on an AI provider or a web API. A profile may
    point at a bundled/local encoder such as FFmpeg, but the core only manages
    the process lifecycle and never downloads or authenticates with a service.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._process: Popen[str] | None = None
        self._state = MediaSessionState.STOPPED
        self._error: str | None = None

    def start(self, profile: MediaProfile) -> MediaSessionSnapshot:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return self.snapshot()
            self._state = MediaSessionState.STARTING
            self._error = None
            try:
                executable = self._resolve_executable(profile.executable)
                self._process = Popen(
                    [executable, *profile.arguments],
                    cwd=profile.working_directory,
                    stdin=PIPE,
                    stdout=PIPE,
                    stderr=PIPE,
                    text=True,
                    bufsize=1,
                    creationflags=self._windows_creation_flags(),
                )
            except (OSError, ValueError) as exc:
                self._process = None
                self._state = MediaSessionState.FAILED
                self._error = str(exc)
                return self.snapshot()
            self._state = MediaSessionState.RUNNING
            return self.snapshot()

    def stop(self, timeout: float = 2.0) -> MediaSessionSnapshot:
        if timeout < 0:
            raise ValueError("timeout must be >= 0")
        with self._lock:
            process = self._process
            if process is None:
                self._state = MediaSessionState.STOPPED
                return self.snapshot()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=timeout)
                except TimeoutExpired:
                    process.kill()
                    try:
                        process.wait(timeout=timeout)
                    except TimeoutExpired:
                        self._state = MediaSessionState.FAILED
                        self._error = "El proceso de transmisión no terminó a tiempo"
                        return self.snapshot()
            self._process = None
            self._state = MediaSessionState.STOPPED
            return self.snapshot()

    def snapshot(self) -> MediaSessionSnapshot:
        with self._lock:
            process = self._process
            if process is not None:
                returncode = process.poll()
                if returncode is not None and self._state == MediaSessionState.RUNNING:
                    self._process = None
                    self._state = MediaSessionState.FAILED if returncode else MediaSessionState.STOPPED
                    if returncode:
                        self._error = f"El proceso terminó con código {returncode}"
                    returncode_value = returncode
                else:
                    returncode_value = returncode
            else:
                returncode_value = None
            return MediaSessionSnapshot(self._state, returncode_value, self._error)

    @staticmethod
    def _resolve_executable(executable: str) -> str:
        if not executable.strip():
            raise ValueError("executable must not be empty")
        candidate = Path(executable)
        if candidate.is_absolute() or candidate.parent != Path("."):
            if not candidate.exists():
                raise FileNotFoundError(f"No existe el ejecutable local: {candidate}")
            return str(candidate)
        return executable

    @staticmethod
    def _windows_creation_flags() -> int:
        if os.name != "nt":
            return 0
        return getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0)
