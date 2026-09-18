import asyncio

import pytest

from app.core.tasks import TaskSupervisor


@pytest.mark.asyncio
async def test_supervisor_rejects_duplicate_running_task() -> None:
    supervisor = TaskSupervisor()
    blocker = asyncio.Event()

    supervisor.start("worker", blocker.wait())
    with pytest.raises(ValueError):
        supervisor.start("worker", blocker.wait())

    await supervisor.stop_all()


@pytest.mark.asyncio
async def test_supervisor_stops_owned_tasks() -> None:
    supervisor = TaskSupervisor()
    blocker = asyncio.Event()
    supervisor.start("worker", blocker.wait())

    assert supervisor.running("worker")
    await supervisor.stop("worker")
    assert not supervisor.running("worker")


@pytest.mark.asyncio
async def test_old_completion_callback_cannot_remove_replacement_task() -> None:
    supervisor = TaskSupervisor()
    first = supervisor.start("worker", asyncio.sleep(0))
    await first

    second = supervisor.start("worker", asyncio.sleep(60))
    supervisor._finish("worker", first)

    assert supervisor.running("worker")
    assert supervisor.names() == ("worker",)

    await supervisor.stop_all()
