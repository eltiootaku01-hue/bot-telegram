# -*- coding: utf-8 -*-
"""Phase 1B Experiment 13: exclude GUI-heavy tests and probe Thread bootstrap."""

from __future__ import annotations

import threading

TARGET = "test_adapter_close_stops_xp_writer_thread"


def pytest_runtest_setup(item):
    if item.name != TARGET:
        return

    state = {"ran": False}

    def worker():
        state["ran"] = True

    thread = threading.Thread(target=worker, name="phase1b-post-gui-exclusion")
    thread.start()
    thread.join()
    print(
        "POST_EXCLUSION_THREAD "
        f"ident={thread.ident} native_id={getattr(thread, 'native_id', None)} "
        f"alive={thread.is_alive()} ran={state['ran']}"
    )
    assert state["ran"] is True
