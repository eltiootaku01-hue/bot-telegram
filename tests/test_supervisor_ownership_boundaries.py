# -*- coding: utf-8 -*-
"""Pruebas read-only de ownership entre Supervisor, runtime y GUI."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_gui_has_distinct_taskengine_scheduler_and_async_orchestrator_paths() -> None:
    app = _read("src/gui/app.py")

    assert "self.runtime.task_engine.create_task(" in app
    assert "self.runtime.task_scheduler.schedule(" in app
    assert "self.runtime.task_scheduler.dispatch()" in app

    assert "orchestrator = TaskOrchestrator(" in app
    assert "web_queue = WebQueueManager()" in app
    assert "web_worker_callback=web_queue.process_task" in app
    assert "orchestrator.enqueue_task(" in app


def test_task_orchestrator_is_not_bound_to_taskengine_contract_or_supervisor() -> None:
    source = _read("src/gui/task_orchestrator.py")

    assert "TaskEngine" not in source
    assert "TaskScheduler" not in source
    assert "TaskContractStore" not in source
    assert "SupervisorCommand" not in source
    assert "ScopeLock" not in source
    assert "Authorization" not in source

    assert "asyncio.PriorityQueue" in source
    assert "WEB_TIMEOUT_SECONDS = 12.0" in source
    assert "CircuitBreaker" in source


def test_task_orchestrator_queue_identity_is_gui_specific() -> None:
    source = _read("src/gui/task_orchestrator.py")

    assert "waitress_id: str" in source
    assert "payload: Dict[str, Any]" in source
    assert "task_id:" not in source
    assert "session_id:" not in source


def test_supervisor_has_no_direct_gui_or_webqueue_handoff() -> None:
    supervisor_paths = (
        "src/bot_ia/supervisor/core.py",
        "src/bot_ia/supervisor/boundary.py",
        "src/bot_ia/supervisor/authorization.py",
        "src/bot_ia/supervisor/task_contract.py",
        "src/bot_ia/supervisor/runtime_observation.py",
    )

    forbidden = (
        "gui.task_orchestrator",
        "TaskOrchestrator",
        "services.web_queue",
        "WebChatQueueManager",
    )

    for relative_path in supervisor_paths:
        source = _read(relative_path)
        for marker in forbidden:
            assert marker not in source, f"{relative_path} unexpectedly references {marker}"


def test_task_scheduler_ownership_is_runtime_local_not_global() -> None:
    scheduler = _read("src/bot_ia/core/task_scheduler.py")
    app = _read("src/gui/app.py")

    assert "class TaskScheduler" in scheduler
    assert "TaskEngine" in scheduler
    assert "self.runtime.task_scheduler" in app
    assert "TaskOrchestrator" in app
