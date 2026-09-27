# -*- coding: utf-8 -*-
"""Phase 1B Experiment 18: Telegram instance lock followed by Thread.start()."""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from bot_ia.interfaces.telegram_instance_lock import (
    TelegramInstanceAlreadyRunning,
    TelegramInstanceLock,
)


def test_singleton_lock_then_thread_bootstrap():
    with tempfile.TemporaryDirectory(prefix="phase1b-lock-") as directory:
        root = Path(directory)
        first = TelegramInstanceLock("token-A", root)
        second = TelegramInstanceLock("token-A", root)

        first.acquire()
        try:
            try:
                second.acquire()
            except TelegramInstanceAlreadyRunning:
                pass
            else:
                raise AssertionError("second lock unexpectedly acquired")
        finally:
            first.release()

        second.acquire()
        second.release()

        state = {"ran": False}

        def worker():
            state["ran"] = True

        thread = threading.Thread(
            target=worker,
            name="phase1b-after-singleton-lock",
        )
        thread.start()
        thread.join()
        assert state["ran"] is True
        assert thread.is_alive() is False
