# -*- coding: utf-8 -*-
"""Phase 1B Experiment 02: thread lifecycle without SQLite."""

from __future__ import annotations

import os
import platform
import sys
from threading import Event, Thread


def test_thread_lifecycle_event_join():
    print(f"PYTHON_VERSION={sys.version}")
    print(f"PLATFORM={platform.platform()}")

    stop = Event()
    state = {"entered": False}

    def worker():
        state["entered"] = True
        stop.wait()

    thread = Thread(target=worker, name="phase1b-lifecycle-thread", daemon=True)
    thread.start()
    assert thread.is_alive() is True

    stop.set()
    thread.join()
    assert state["entered"] is True
    assert thread.is_alive() is False
