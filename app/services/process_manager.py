from __future__ import annotations

from subprocess import PIPE, Popen, TimeoutExpired
from threading import RLock
from typing import Callable, Sequence

from app.services.process_health import HealthResult, ProcessHealth
from app.services.process_reader import ProcessOutput, ProcessReader
from app.services.startup_sequence import StartupResult, StartupSequence


class ProcessManager:
    """Own subprocess launch, output capture and fail-fast startup policy."""

    def __init__(
        self,
        command: Callable[[str], Sequence[str]],
        cwd: str | None = None,
        grace_seconds: float = 2.0,
        stop_timeout: float = 2.0,
    ) -> None:
        if stop_timeout < 0:
            raise ValueError("stop_timeout must be >= 0")
        self.command = command
        self.cwd = cwd
        self.stop_timeout = stop_timeout
        self.reader = ProcessReader()
        self.health = ProcessHealth(self.reader, grace_seconds=grace_seconds)
        self._lock = RLock()
        self.processes: dict[str, Popen[str]] = {}
        self.last_output: dict[str, tuple[ProcessOutput, ...]] = {}

    def launch(self, identity: str) -> Popen[str]:
        with self._lock:
            existing = self.processes.get(identity)
            if existing is not None and existing.poll() is None:
                return existing
            process = Popen(
                list(self.command(identity)),
                stdout=PIPE,
                stderr=PIPE,
                cwd=self.cwd,
                text=True,
                bufsize=1,
            )
            self.reader.attach(identity, process)
            self.processes[identity] = process
            return process

    def check_health(self, identity: str, process: Popen[str]) -> bool:
        result = self.health.check(identity, process)
        with self._lock:
            self.last_output[identity] = result.output
        return result.healthy

    def stop(self, identity: str, process: Popen[str]) -> None:
        with self._lock:
            managed = self.processes.get(identity)
            target = managed if managed is not None else process

        if target.poll() is None:
            target.terminate()
            try:
                target.wait(timeout=self.stop_timeout)
            except TimeoutExpired:
                target.kill()
                try:
                    target.wait(timeout=self.stop_timeout)
                except TimeoutExpired:
                    # Keep the process registered: claiming it stopped while it is
                    # still alive would make the dashboard and future controls lie.
                    return

        with self._lock:
            if self.processes.get(identity) is target:
                self.processes.pop(identity, None)

    def start_sequential(self, identities: Sequence[str]) -> StartupResult:
        sequence = StartupSequence(identities, self.launch, self.check_health, self.stop)
        result = sequence.run()
        if result.failure is not None:
            events = self.reader.drain()
            if events:
                with self._lock:
                    existing = self.last_output.get(result.failure.identity, ())
                    self.last_output[result.failure.identity] = existing + tuple(
                        event for event in events if event.identity == result.failure.identity
                    )
        return result

    def drain_output(self) -> list[ProcessOutput]:
        events = self.reader.drain()
        if not events:
            return []
        with self._lock:
            for event in events:
                self.last_output[event.identity] = self.last_output.get(event.identity, ()) + (event,)
        return events

    def stop_all(self) -> None:
        with self._lock:
            processes = list(self.processes.items())
        for identity, process in processes:
            self.stop(identity, process)

    def health_details(self, identity: str) -> HealthResult | None:
        with self._lock:
            output = self.last_output.get(identity)
            process = self.processes.get(identity)
        if output is None:
            return None
        return HealthResult(
            healthy=process is not None and process.poll() is None,
            returncode=None if process is None else process.poll(),
            output=output,
        )
