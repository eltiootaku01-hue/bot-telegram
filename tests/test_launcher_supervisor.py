from __future__ import annotations

import sys
import time
from threading import Event, Thread

from app.services.launcher_supervisor import LauncherSupervisor
from app.services.startup_sequence import StartupResult
from app.services.process_manager import ProcessManager
from app.services.startup_sequence import StartupSequence


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


def test_supervisor_preserves_fail_fast_startup_result() -> None:
    manager = ProcessManager(
        lambda identity: [
            sys.executable,
            "-c",
            "import sys; print('startup failed', flush=True); sys.exit(9)"
            if identity == "cari"
            else "import time; time.sleep(10)",
        ],
        grace_seconds=0.05,
        stop_timeout=0.5,
    )
    supervisor = LauncherSupervisor(manager)

    assert supervisor.start_all(("cari", "sunna"))
    result = wait_result(supervisor)

    assert result.error is None
    assert result.result is not None
    assert result.result.started == ()
    assert result.result.failure is not None
    assert result.result.failure.identity == "cari"
    assert result.result.failure.returncode == 9
    assert "sunna" not in manager.processes


def test_startup_sequence_cancels_before_launching_next_identity() -> None:
    launched: list[str] = []
    stopped: list[str] = []
    continue_state = {"value": True}

    def launch(identity: str) -> object:
        launched.append(identity)
        continue_state["value"] = False
        return object()

    def health(_: str, __: object) -> bool:
        return True

    def stop(identity: str, _: object) -> None:
        stopped.append(identity)

    sequence = StartupSequence(
        ("cari", "sunna", "cami"),
        launch,
        health,
        stop,
        lambda: continue_state["value"],
    )

    result = sequence.run()

    assert result.cancelled is True
    assert result.failure is None
    assert result.started == ()
    assert launched == ["cari"]
    assert stopped == ["cari"]


def test_supervisor_stop_all_cancels_pending_startup() -> None:
    manager = ProcessManager(
        lambda _: [sys.executable, "-c", "import time; time.sleep(10)"],
        grace_seconds=0.5,
        stop_timeout=0.5,
    )
    supervisor = LauncherSupervisor(manager)

    assert supervisor.start_all(("cari", "sunna"))
    time.sleep(0.05)
    supervisor.stop_all()

    result = wait_result(supervisor)
    assert result.error is None
    assert result.result is not None
    assert result.result.cancelled is True
    assert result.result.failure is None
    assert result.result.started == ()
    assert manager.active_processes() == {}



def test_supervisor_cleans_up_if_startup_raises_outside_sequence_handling() -> None:
    class FailingManager:
        def __init__(self) -> None:
            self.stopped = False

        def start_sequential(self, identities, launch, should_continue):
            raise RuntimeError("unexpected supervisor failure")

        def stop_all(self) -> None:
            self.stopped = True

    manager = FailingManager()
    supervisor = LauncherSupervisor(manager)  # type: ignore[arg-type]

    assert supervisor.start_all(("cari",))
    result = wait_result(supervisor)

    assert isinstance(result.error, RuntimeError)
    assert str(result.error) == "unexpected supervisor failure"
    assert manager.stopped is True




def test_supervisor_waits_for_startup_worker() -> None:
    release = Event()

    class SlowManager:
        def start_sequential(self, identities, launch, should_continue):
            release.wait(timeout=2)
            return StartupResult((), cancelled=not should_continue())

        def stop_all(self) -> None:
            release.set()

    supervisor = LauncherSupervisor(SlowManager())  # type: ignore[arg-type]

    assert supervisor.start_all(("cari",))
    assert supervisor.running
    assert supervisor.stop_all() is True
    assert not supervisor.running


def test_supervisor_stop_all_closes_launch_race() -> None:
    launch_entered = Event()
    release_launch = Event()

    class Manager:
        def __init__(self) -> None:
            self.launched: list[str] = []
            self.stopped = False

        def launch(self, identity: str):
            self.launched.append(identity)
            launch_entered.set()
            assert release_launch.wait(timeout=2)
            return object()

        def start_sequential(self, identities, launch, should_continue):
            launch(identities[0])
            if not should_continue():
                return StartupResult((), cancelled=True)
            return StartupResult((identities[0],))

        def stop_all(self) -> None:
            self.stopped = True

    manager = Manager()
    supervisor = LauncherSupervisor(manager)  # type: ignore[arg-type]
    assert supervisor.start_all(("cari",))
    assert launch_entered.wait(timeout=2)

    stopper = Thread(target=supervisor.stop_all, daemon=True)
    stopper.start()
    time.sleep(0.02)
    release_launch.set()
    stopper.join(timeout=2)
    assert not stopper.is_alive()

    result = wait_result(supervisor)
    assert result.result is not None
    assert result.result.cancelled is True
    assert manager.launched == ["cari"]
    assert manager.stopped is True
