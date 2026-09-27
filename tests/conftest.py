# -*- coding: utf-8 -*-
"""Phase 1B Experiment 06: move the failing adapter test to first position."""

from __future__ import annotations


TARGET = (
    "tests/test_telegram_runtime_safety.py::"
    "TelegramRuntimeSafetyTests::test_adapter_close_stops_xp_writer_thread"
)


def pytest_collection_modifyitems(_config, items):
    items.sort(key=lambda item: 0 if item.nodeid == TARGET else 1)
