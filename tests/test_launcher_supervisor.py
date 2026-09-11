from __future__ import annotations

import sys
import time

from app.services.launcher_supervisor import LauncherSupervisor
from app.services.process_manager import ProcessManager


def wait_result(supervisor: LauncherSupervisor):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        result = supervisor.poll_result()
        if result is not None:
            return result
        time.sleep(0.01)
    raise AssertionError("supervisor did not publish a result")


def test_supervisor_runs_startup_off_caller_thread() -> None:
    manager = ProcessManager(
        lambda _: [sys.executable, "-c", "import time; time.sleep(.15)"],
        grace_seconds=0.05,
        stop_timeout=0.5,
    )
    supervisor = LauncherSupervisor(manager)

    started_at = time.monotonic()
    assert supervisor.start_all(("cari",))
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.05
    result = wait_result(supervisor)
    assert result.error is None
    assert result.result is not None
    assert result.result.started == ("cari",)
    manager.stop_all()


def test_supervisor_rejects_parallel_start_requests() -> None:
    manager = ProcessManager(
        lambda _: [sys.executable, "-c", "import time; time.sleep(.2)"],
        grace_seconds=0.05,
        stop_timeout=0.5,
    )
    supervisor = LauncherSupervisor(manager)

    assert supervisor.start_all(("cari",))
    assert not supervisor.start_all(("sunna",))
    result = wait_result(supervisor)
    assert result.error is None
    manager.stop_all()
