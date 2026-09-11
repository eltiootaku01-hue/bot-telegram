from __future__ import annotations

import sys
import time

import pytest

from app.services.process_manager import ProcessManager


def test_process_manager_rejects_negative_stop_timeout() -> None:
    with pytest.raises(ValueError, match="stop_timeout"):
        ProcessManager(lambda _: [sys.executable, "-c", "pass"], stop_timeout=-1)


def test_process_manager_stops_process_and_clears_registry() -> None:
    manager = ProcessManager(
        lambda _: [sys.executable, "-c", "import time; time.sleep(10)"],
        grace_seconds=0,
        stop_timeout=0.5,
    )
    process = manager.launch("cari")
    assert process.poll() is None
    manager.stop("cari", process)
    assert process.poll() is not None
    assert "cari" not in manager.processes


def test_process_manager_can_restart_after_a_clean_stop() -> None:
    starts = 0

    def command(_: str) -> list[str]:
        nonlocal starts
        starts += 1
        return [sys.executable, "-c", "import time; time.sleep(10)"]

    manager = ProcessManager(command, grace_seconds=0, stop_timeout=0.5)
    first = manager.launch("cari")
    manager.stop("cari", first)
    assert "cari" not in manager.processes

    second = manager.launch("cari")
    assert second is not first
    assert starts == 2
    assert second.poll() is None
    time.sleep(0.01)
    manager.stop_all()
    assert not manager.processes
