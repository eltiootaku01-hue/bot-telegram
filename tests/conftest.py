# -*- coding: utf-8 -*-
"""Phase 1B Experiment 07: process-state diagnostics before Thread.start()."""

from __future__ import annotations

import ctypes
import gc
import os
import platform
import sys
import threading
from pathlib import Path


TARGET = (
    "tests/test_telegram_runtime_safety.py::"
    "TelegramRuntimeSafetyTests::test_adapter_close_stops_xp_writer_thread"
)
LOG = Path("phase1b_state.log")


def _rss_bytes() -> int | None:
    if os.name != "nt":
        try:
            with open("/proc/self/statm", encoding="ascii") as handle:
                pages = int(handle.read().split()[1])
            return pages * os.sysconf("SC_PAGE_SIZE")
        except Exception:
            return None

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(Counters)
    process = ctypes.windll.kernel32.GetCurrentProcess()
    psapi = ctypes.windll.psapi
    if not psapi.GetProcessMemoryInfo(
        process,
        ctypes.byref(counters),
        counters.cb,
    ):
        return None
    return int(counters.WorkingSetSize)


def _snapshot(label: str) -> None:
    line = (
        "PHASE1B_MEMORY "
        f"label={label} "
        f"python={sys.version.split()[0]} "
        f"platform={platform.platform()} "
        f"rss={_rss_bytes()} "
        f"allocated_blocks={getattr(sys, 'getallocatedblocks', lambda: None)()} "
        f"gc_count={gc.get_count()} "
        f"thread_stack_size={threading.stack_size()} "
        f"threads={len(threading.enumerate())} "
        f"active={len(getattr(threading, '_active', {}))} "
        f"limbo={len(getattr(threading, '_limbo', {}))} "
        f"dangling={len(getattr(threading, '_dangling', ()))}"
    )
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()


def pytest_sessionstart(session):
    LOG.write_text("", encoding="utf-8")
    _snapshot("session_start")


def pytest_runtest_protocol(item, nextitem):
    if item.nodeid == TARGET:
        _snapshot("before_failing_test")
    return None
