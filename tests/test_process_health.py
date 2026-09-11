from __future__ import annotations

from subprocess import PIPE, Popen

from app.services.process_health import ProcessHealth
from app.services.process_reader import ProcessReader


def test_health_rejects_process_that_exits_early() -> None:
    reader = ProcessReader()
    process = Popen(
        ["python", "-c", "import sys; print('startup failed'); print('fatal', file=sys.stderr); sys.exit(7)"],
        stdout=PIPE,
        stderr=PIPE,
        text=True,
    )
    reader.attach("cari", process)
    process.wait(timeout=5)

    result = ProcessHealth(reader, grace_seconds=0.01).check("cari", process)

    assert result.healthy is False
    assert result.returncode == 7
    assert {(event.stream, event.line) for event in result.output} == {
        ("stdout", "startup failed"),
        ("stderr", "fatal"),
    }


def test_health_accepts_process_that_stays_alive() -> None:
    reader = ProcessReader()
    process = Popen(
        ["python", "-c", "import time; print('ready', flush=True); time.sleep(1)"],
        stdout=PIPE,
        stderr=PIPE,
        text=True,
    )
    reader.attach("sunna", process)

    result = ProcessHealth(reader, grace_seconds=0.02).check("sunna", process)
    process.terminate()
    process.wait(timeout=5)

    assert result.healthy is True
    assert result.returncode is None
    assert any(event.line == "ready" for event in result.output)
