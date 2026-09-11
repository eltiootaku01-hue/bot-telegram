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
    ) -> None:
        self.command = command
        self.cwd = cwd
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

    def check_health(self, identity: str, process: object) -> bool:
        result = self.health.check(identity, process)  # type: ignore[arg-type]
        self.last_output[identity] = result.output
        return result.healthy

    def stop(self, identity: str, process: object) -> None:
        managed = process if isinstance(process, Popen) else self.processes.get(identity)
        if managed is not None and managed.poll() is None:
            managed.terminate()
        self.processes.pop(identity, None)

    def start_sequential(self, identities: Sequence[str]) -> StartupResult:
        sequence = StartupSequence(identities, self.launch, self.check_health, self.stop)
        result = sequence.run()
        if result.failure is not None:
            self.last_output[result.failure.identity] = tuple(self.reader.drain())
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
