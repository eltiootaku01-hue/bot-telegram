# -*- coding: utf-8 -*-
"""Phase 1B Experiment 10: prove a trivial thread can start immediately before the target."""

from __future__ import annotations

from threading import Thread

TARGET = (
    "tests/test_telegram_runtime_safety.py::"
    "TelegramRuntimeSafetyTests::test_adapter_close_stops_xp_writer_thread"
)


def pytest_runtest_setup(item):
    if item.nodeid != TARGET:
        return

    state = {"ran": False}

    def worker():
        state["ran"] = True

    thread = Thread(target=worker, name="phase1b-immediate-minimal")
    print(
        "BEFORE_IMMEDIATE_THREAD "
        f"name={thread.name} ident={thread.ident} "
        f"native_id={getattr(thread, 'native_id', None)} "
        f"alive={thread.is_alive()} daemon={thread.daemon}"
    )
    thread.start()
    print(
        "AFTER_IMMEDIATE_THREAD_START "
        f"name={thread.name} ident={thread.ident} "
        f"native_id={getattr(thread, 'native_id', None)} "
        f"alive={thread.is_alive()} daemon={thread.daemon}"
    )
    thread.join()
    print(
        "AFTER_IMMEDIATE_THREAD_JOIN "
        f"name={thread.name} ident={thread.ident} "
        f"native_id={getattr(thread, 'native_id', None)} "
        f"alive={thread.is_alive()} daemon={thread.daemon} ran={state['ran']}"
    )
    assert state["ran"] is True
