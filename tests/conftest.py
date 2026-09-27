# -*- coding: utf-8 -*-
"""Phase 1B Experiment 17: isolate the Telegram integrity test that breaks bootstrap."""

from __future__ import annotations

import threading
from pathlib import Path


LOG = Path("phase1b_telegram_integrity_probes.log")


def pytest_sessionstart(session):
    LOG.write_text("", encoding="utf-8")


def pytest_runtest_teardown(item, nextitem):
    if str(item.fspath).replace("\\", "/").endswith("/tests/test_telegram_integrity.py"):
        state = {"ran": False}

        def worker():
            state["ran"] = True

        thread = threading.Thread(
            target=worker,
            name="phase1b-after-telegram-integrity-test",
        )
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(
                f"BEFORE node={item.nodeid}\n"
            )
            handle.flush()
            import os
            os.fsync(handle.fileno())

        thread.start()
        thread.join()

        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(
                f"AFTER node={item.nodeid} ident={thread.ident} "
                f"native_id={getattr(thread, 'native_id', None)} "
                f"alive={thread.is_alive()} ran={state['ran']}\n"
            )
            handle.flush()
            import os
            os.fsync(handle.fileno())
