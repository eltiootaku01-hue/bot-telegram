from __future__ import annotations

from dataclasses import dataclass
from subprocess import Popen
from time import monotonic, sleep

from app.services.process_reader import ProcessOutput, ProcessReader


@dataclass(frozen=True, slots=True)
class HealthResult:
    healthy: bool
    returncode: int | None = None
    output: tuple[ProcessOutput, ...] = ()


class ProcessHealth:
    """Deterministic startup health check for a managed subprocess.

    A process is considered healthy when it remains alive for the configured
    grace period. Any early exit is a startup failure and its captured output
    is returned verbatim for diagnostics.
    """

    _OUTPUT_FLUSH_DELAY = 0.01

    def __init__(self, reader: ProcessReader, grace_seconds: float = 2.0) -> None:
        if grace_seconds < 0:
            raise ValueError("grace_seconds must be >= 0")
        self.reader = reader
        self.grace_seconds = grace_seconds

    def check(self, identity: str, process: Popen[str]) -> HealthResult:
        del identity
        deadline = monotonic() + self.grace_seconds
        captured: list[ProcessOutput] = []
        while monotonic() < deadline:
            captured.extend(self.reader.drain())
            returncode = process.poll()
            if returncode is not None:
                self._flush_reader(captured)
                return HealthResult(False, returncode, tuple(captured))
            sleep(0.01)

        self._flush_reader(captured)
        returncode = process.poll()
        if returncode is not None:
            self._flush_reader(captured)
            return HealthResult(False, returncode, tuple(captured))
        return HealthResult(True, None, tuple(captured))

    def _flush_reader(self, captured: list[ProcessOutput]) -> None:
        sleep(self._OUTPUT_FLUSH_DELAY)
        captured.extend(self.reader.drain())
