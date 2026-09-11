from __future__ import annotations

import sys
import time

from app.services.launcher_supervisor import LauncherSupervisor, StartupTaskResult
from app.services.process_manager import ProcessManager


def test_supervisor_runs_startup_off_caller_thread() -> None:
    manager = ProcessManager(
        lambda _: [sys.executable, "-c", "import time; time.sleep(.15)"],
        grace_seconds=0.05,
        stop_timeout=0.5,
    )
    supervisor = LauncherSupervisor(manager)
    results: list[StartupTaskResult] = []

    started_at = time.monotonic()
    assert supervisor.start_all(("cari",), results.append)
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.05
    deadline = time.monotonic() + 2
    while not results and time.monotonic() < deadline:
        time.sleep(0.01)
    assert results
    assert results[0].error is None
    assert results[0].result is not None
    assert results[0].result.started == ("cari",)
    manager.stop_all()


def test_supervisor_rejects_parallel_start_requests() -> None:
    manager = ProcessManager(
        lambda _: [sys.executable, "-c", "import time; time.sleep(.2)"],
        grace_seconds=0.05,
        stop_timeout=0.5,
    )
    supervisor = LauncherSupervisor(manager)
    results: list[StartupTaskResult] = []

    assert supervisor.start_all(("cari",), results.append)
    assert not supervisor.start_all(("sunna",), results.append)
    deadline = time.monotonic() + 2
    while not results and time.monotonic() < deadline:
        time.sleep(0.01)
    manager.stop_all()
