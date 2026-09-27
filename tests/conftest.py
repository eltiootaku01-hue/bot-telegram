# -*- coding: utf-8 -*-
"""Phase 1B Experiment 08: force GC immediately before the failing test."""

from __future__ import annotations

import gc
from pathlib import Path


TARGET = (
    "tests/test_telegram_runtime_safety.py::"
    "TelegramRuntimeSafetyTests::test_adapter_close_stops_xp_writer_thread"
)
LOG = Path("phase1b_gc.log")


def pytest_sessionstart(session):
    LOG.write_text("", encoding="utf-8")


def pytest_runtest_protocol(item, nextitem):
    if item.nodeid == TARGET:
        before = gc.get_count()
        collected = gc.collect(2)
        after = gc.get_count()
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(
                f"target_gc before={before} collected={collected} after={after}\n"
            )
            handle.flush()
    return None
