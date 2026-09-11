from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Queue
from subprocess import Popen
from threading import Thread


@dataclass(frozen=True, slots=True)
class ProcessOutput:
    identity: str
    stream: str
    line: str


class ProcessReader:
    """Non-blocking stdout/stderr reader for managed bot processes."""

    def __init__(self) -> None:
        self.events: Queue[ProcessOutput] = Queue()

    def attach(self, identity: str, process: Popen[str]) -> None:
        for stream_name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            if stream is None:
                continue
            Thread(
                target=self._read,
                args=(identity, stream_name, stream),
                daemon=True,
                name=f"bot-reader-{identity}-{stream_name}",
            ).start()

    def _read(self, identity: str, stream_name: str, stream) -> None:
        try:
            for line in iter(stream.readline, ""):
                text = line.rstrip("\r\n")
                if text:
                    self.events.put(ProcessOutput(identity, stream_name, text))
        finally:
            stream.close()

    def drain(self) -> list[ProcessOutput]:
        result: list[ProcessOutput] = []
        while True:
            try:
                result.append(self.events.get_nowait())
            except Empty:
                return result
