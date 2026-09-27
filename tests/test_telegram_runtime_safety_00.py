# -*- coding: utf-8 -*-
"""Phase 1B Experiment 10: trivial Thread immediately before the target."""

from __future__ import annotations

from threading import Thread


def test_minimal_thread_immediately_before_telegram_runtime_safety():
    state = {"ran": False}

    def worker():
        state["ran"] = True

    thread = Thread(target=worker, name="phase1b-immediate-minimal")
    thread.start()
    thread.join()
    assert state["ran"] is True
    assert thread.is_alive() is False
