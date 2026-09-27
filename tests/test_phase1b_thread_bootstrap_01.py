# -*- coding: utf-8 -*-
"""Phase 1B Experiment 01: minimal Windows thread bootstrap."""

from __future__ import annotations

import os
import platform
import sys
from threading import Thread


def test_minimal_thread_bootstrap():
    print(f"PYTHON_VERSION={sys.version}")
    print(f"PYTHON_IMPLEMENTATION={platform.python_implementation()}")
    print(f"OS={os.name}")
    print(f"PLATFORM={platform.platform()}")

    state = {"started": False}

    def worker():
        state["started"] = True

    thread = Thread(target=worker, name="phase1b-minimal-thread")
    print(
        "BEFORE_START "
        f"name={thread.name} ident={thread.ident} "
        f"native_id={getattr(thread, 'native_id', None)} "
        f"alive={thread.is_alive()} daemon={thread.daemon}"
    )
    thread.start()
    print(
        "AFTER_START "
        f"name={thread.name} ident={thread.ident} "
        f"native_id={getattr(thread, 'native_id', None)} "
        f"alive={thread.is_alive()} daemon={thread.daemon}"
    )
    thread.join()
    print(
        "AFTER_JOIN "
        f"name={thread.name} ident={thread.ident} "
        f"native_id={getattr(thread, 'native_id', None)} "
        f"alive={thread.is_alive()} daemon={thread.daemon} "
        f"worker_ran={state['started']}"
    )

    assert state["started"] is True
