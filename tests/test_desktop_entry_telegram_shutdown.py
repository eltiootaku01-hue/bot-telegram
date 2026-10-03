# -*- coding: utf-8 -*-
from __future__ import annotations

from contextlib import contextmanager
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import desktop_entry


class _FakePoller:
    def __init__(self, *args, **kwargs):
        self.stop_calls = 0
        self.run_error = None

    def stop(self):
        self.stop_calls += 1

    def run(self):
        if self.run_error is not None:
            raise self.run_error
        return SimpleNamespace(
            polls=1,
            updates_received=0,
            updates_processed=0,
            responses_sent=0,
            transport_errors=0,
        )


def test_sigint_handler_requests_poller_stop_and_restore():
    poller = _FakePoller()
    previous = object()
    installed = {}

    def fake_getsignal(signum):
        return previous

    def fake_signal(signum, handler):
        installed[signum] = handler

    with (
        patch.object(desktop_entry.signal, "getsignal", side_effect=fake_getsignal),
        patch.object(desktop_entry.signal, "signal", side_effect=fake_signal),
    ):
        restore = desktop_entry._install_telegram_signal_handlers(poller)
        installed[desktop_entry.signal.SIGINT](desktop_entry.signal.SIGINT, None)
        restore()

    assert poller.stop_calls == 1
    assert installed[desktop_entry.signal.SIGINT] is previous
    assert installed[desktop_entry.signal.SIGTERM] is previous


def test_sigterm_handler_requests_poller_stop():
    poller = _FakePoller()
    handlers = {}

    def fake_signal(signum, handler):
        handlers[signum] = handler

    with (
        patch.object(desktop_entry.signal, "getsignal", return_value=None),
        patch.object(desktop_entry.signal, "signal", side_effect=fake_signal),
    ):
        restore = desktop_entry._install_telegram_signal_handlers(poller)
        handlers[desktop_entry.signal.SIGTERM](desktop_entry.signal.SIGTERM, None)
        restore()

    assert poller.stop_calls == 1


def test_sigbreak_handler_requests_poller_stop_when_available():
    sigbreak = getattr(desktop_entry.signal, "SIGBREAK", None)
    if sigbreak is None:
        return

    poller = _FakePoller()
    handlers = {}

    def fake_signal(signum, handler):
        handlers[signum] = handler

    with (
        patch.object(desktop_entry.signal, "getsignal", return_value=None),
        patch.object(desktop_entry.signal, "signal", side_effect=fake_signal),
    ):
        restore = desktop_entry._install_telegram_signal_handlers(poller)
        handlers[sigbreak](sigbreak, None)
        restore()

    assert poller.stop_calls == 1


def _fake_runtime_modules(poller):
    telegram_module = ModuleType("bot_ia.interfaces.telegram")
    telegram_module.TelegramApiClient = SimpleNamespace(
        from_environment=lambda: SimpleNamespace(smoke_test=lambda: True)
    )
    telegram_module.TelegramPoller = lambda *args, **kwargs: poller

    outbox_module = ModuleType("bot_ia.interfaces.telegram_outbox")
    outbox_module.TelegramOutboxStore = lambda _path: object()

    projects_module = ModuleType("bot_ia.interfaces.telegram_projects")
    projects_module.TelegramProjectsAdapter = lambda application, runtime: object()

    runtime_module = ModuleType("bot_ia.runtime")

    class FakeRuntime:
        def __init__(self):
            self.memory_store = SimpleNamespace(
                path="memory.sqlite3",
                close=lambda: setattr(self.memory_store, "closed", True),
                closed=False,
            )

        def build_application(self, **_kwargs):
            return object()

    fake_runtime = FakeRuntime()
    runtime_module.build_runtime = lambda _root: fake_runtime

    return {
        "bot_ia.interfaces.telegram": telegram_module,
        "bot_ia.interfaces.telegram_outbox": outbox_module,
        "bot_ia.interfaces.telegram_projects": projects_module,
        "bot_ia.runtime": runtime_module,
    }, fake_runtime


def test_worker_finally_stops_poller_restores_handlers_and_closes_runtime():
    poller = _FakePoller()
    poller.run_error = RuntimeError("forced worker failure")
    modules, runtime = _fake_runtime_modules(poller)
    restore_calls = []

    with (
        patch.dict("sys.modules", modules),
        patch.object(
            desktop_entry,
            "_install_telegram_signal_handlers",
            side_effect=lambda _poller: restore_calls.append("installed")
            or (lambda: restore_calls.append("restored")),
        ),
        patch.object(desktop_entry, "load_dotenv"),
    ):
        result = desktop_entry._run_telegram_worker()

    assert result == 1
    assert poller.stop_calls == 1
    assert restore_calls == ["installed", "restored"]
    assert runtime.memory_store.closed is True


def test_worker_handles_poller_creation_failure_without_unboundlocalerror():
    modules, runtime = _fake_runtime_modules(_FakePoller())
    modules["bot_ia.interfaces.telegram"].TelegramPoller = lambda *args, **kwargs: (_ for _ in ()).throw(
        RuntimeError("poller construction failed")
    )

    with (
        patch.dict("sys.modules", modules),
        patch.object(desktop_entry, "load_dotenv"),
    ):
        result = desktop_entry._run_telegram_worker()

    assert result == 1
    assert runtime.memory_store.closed is True
