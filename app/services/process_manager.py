from __future__ import annotations

from subprocess import PIPE, Popen
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
        self.processes: dict[str, Popen[str]] = {}
        self.last_output: dict[str, tuple[ProcessOutput, ...]] = {}

    def launch(self, identity: str) -> Popen[str]:
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
        self.last_output[identity] = result.output
        return result.healthy

    def stop(self, identity: str, process: Popen[str]) -> None:
        managed = self.processes.get(identity)
        target = managed if managed is not None else process
        if target.poll() is None:
            target.terminate()
            try:
                target.wait(timeout=self.stop_timeout)
            except TimeoutError:
                target.kill()
                target.wait(timeout=self.stop_timeout)
        self.processes.pop(identity, None)

    def start_sequential(self, identities: Sequence[str]) -> StartupResult:
        sequence = StartupSequence(identities, self.launch, self.check_health, self.stop)
        result = sequence.run()
        if result.failure is not None:
            events = self.reader.drain()
            if events:
                existing = self.last_output.get(result.failure.identity, ())
                self.last_output[result.failure.identity] = existing + tuple(
                    event for event in events if event.identity == result.failure.identity
                )
        return result

    def drain_output(self) -> list[ProcessOutput]:
        events = self.reader.drain()
        for event in events:
            self.last_output[event.identity] = self.last_output.get(event.identity, ()) + (event,)
        return events

    def stop_all(self) -> None:
        for identity, process in list(self.processes.items()):
            self.stop(identity, process)

    def health_details(self, identity: str) -> HealthResult | None:
        output = self.last_output.get(identity)
        if output is None:
            return None
        process = self.processes.get(identity)
        return HealthResult(
            healthy=process is not None and process.poll() is None,
            returncode=None if process is None else process.poll(),
            output=output,
        )
