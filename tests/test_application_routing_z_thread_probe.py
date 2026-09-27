# -*- coding: utf-8 -*-
"""Phase 1B Experiment 15: probe Thread.start() immediately after first test."""

from __future__ import annotations

import threading


def test_thread_bootstrap_after_application_routing():
    state = {"ran": False}

    def worker():
        state["ran"] = True

    thread = threading.Thread(target=worker, name="phase1b-after-first-test")
    print(
        "AFTER_FIRST_TEST_BEFORE_START "
        f"ident={thread.ident} native_id={getattr(thread, 'native_id', None)} "
        f"alive={thread.is_alive()} daemon={thread.daemon}"
    )
    thread.start()
    thread.join()
    print(
        "AFTER_FIRST_TEST_AFTER_JOIN "
        f"ident={thread.ident} native_id={getattr(thread, 'native_id', None)} "
        f"alive={thread.is_alive()} ran={state['ran']}"
    )
    assert state["ran"] is True
