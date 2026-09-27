# -*- coding: utf-8 -*-
"""Phase 1B Experiment 19: os.kill(pid, 0) followed by a Thread."""

from __future__ import annotations

import os
import threading


def test_os_kill_zero_then_thread():
    os.kill(os.getpid(), 0)

    state = {"ran": False}

    def worker():
        state["ran"] = True

    thread = threading.Thread(target=worker, name="phase1b-after-kill-zero")
    thread.start()
    thread.join()

    assert state["ran"] is True
    assert thread.is_alive() is False
