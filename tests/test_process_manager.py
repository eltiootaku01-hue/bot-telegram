from __future__ import annotations

import sys
import time

from app.services.process_manager import ProcessManager


def test_process_manager_captures_failed_startup_output_and_fails_fast() -> None:
    launched: list[str] = []

    def command(identity: str) -> list[str]:
        launched.append(identity)
        if identity == "cari":
            return [
                sys.executable,
                "-c",
                "import sys; print('boot stdout'); print('boot stderr', file=sys.stderr); sys.exit(7)",
            ]
        return [sys.executable, "-c", "import time; time.sleep(10)"]

    manager = ProcessManager(command, grace_seconds=0.2)
    result = manager.start_sequential(("cari", "sunna"))

    assert result.started == ()
    assert result.failure is not None
    assert result.failure.identity == "cari"
    assert result.failure.returncode == 7
    assert launched == ["cari"]
    output = manager.last_output["cari"]
    assert any(item.stream == "stdout" and item.line == "boot stdout" for item in output)
    assert any(item.stream == "stderr" and item.line == "boot stderr" for item in output)
    assert "sunna" not in manager.processes


def test_process_manager_keeps_healthy_process_running() -> None:
    manager = ProcessManager(
        lambda _: [sys.executable, "-c", "import time; print('ready', flush=True); time.sleep(1)"],
        grace_seconds=0.05,
    )

    result = manager.start_sequential(("cari",))

    assert result.failure is None
    assert result.started == ("cari",)
    assert manager.processes["cari"].poll() is None
    assert manager.active_processes()["cari"] is manager.processes["cari"]
    time.sleep(0.01)
    manager.stop_all()
    assert not manager.processes


def test_process_manager_reaps_finished_processes() -> None:
    manager = ProcessManager(
        lambda _: [
            sys.executable,
            "-c",
            "import sys; print('crashed', flush=True); print('error', file=sys.stderr); sys.exit(3)",
        ],
        grace_seconds=0,
    )
    process = manager.launch("cari")
    process.wait(timeout=1)

    finished = manager.reap_finished()

    assert finished == [("cari", 3)]
    assert "cari" not in manager.processes
    exit_info = manager.last_exit_for("cari")
    assert exit_info is not None
    assert exit_info.identity == "cari"
    assert exit_info.returncode == 3
    assert any(item.stream == "stdout" and item.line == "crashed" for item in exit_info.output)
    assert any(item.stream == "stderr" and item.line == "error" for item in exit_info.output)


def test_process_manager_clears_stale_exit_when_process_is_started_again() -> None:
    manager = ProcessManager(
        lambda _: [sys.executable, "-c", "import sys; sys.exit(4)"],
        grace_seconds=0,
    )
    process = manager.launch("cari")
    process.wait(timeout=1)
    assert manager.reap_finished() == [("cari", 4)]
    assert manager.last_exit_for("cari") is not None

    manager.launch("cari")
    assert manager.last_exit_for("cari") is None
    manager.stop_all()
