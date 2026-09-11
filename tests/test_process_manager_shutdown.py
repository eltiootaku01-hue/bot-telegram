from __future__ import annotations

import sys

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
