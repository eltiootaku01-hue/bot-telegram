from __future__ import annotations

from io import StringIO
from subprocess import PIPE, Popen

from app.services.process_reader import ProcessReader


def test_process_reader_captures_stdout_and_stderr() -> None:
    reader = ProcessReader()
    process = Popen(
        ["python", "-c", "import sys; print('ok'); print('bad', file=sys.stderr)"],
        stdout=PIPE,
        stderr=PIPE,
        text=True,
    )
    reader.attach("cari", process)
    process.wait(timeout=5)

    lines = reader.drain()
    assert {event.stream for event in lines} == {"stdout", "stderr"}
    assert {event.line for event in lines} == {"ok", "bad"}


def test_process_reader_drains_without_blocking() -> None:
    reader = ProcessReader()
    assert reader.drain() == []
