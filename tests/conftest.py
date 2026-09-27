# -*- coding: utf-8 -*-
"""Phase 1B Experiment 11: native process resources before Thread.start()."""

from __future__ import annotations

import ctypes
import gc
import os
import sys
import threading
from pathlib import Path


TARGETS = {
    "tests/test_telegram_runtime_safet.py::test_minimal_thread_immediately_before_telegram_runtime_safety",
    "tests/test_telegram_runtime_safety.py::TelegramRuntimeSafetyTests::test_adapter_close_stops_xp_writer_thread",
}
LOG = Path("phase1b_native_resources.log")


def _native_resources():
    if os.name != "nt":
        return {"rss": None, "private": None, "handles": None}

    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
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

    process = ctypes.windll.kernel32.GetCurrentProcess()
    counters = Counters()
    counters.cb = ctypes.sizeof(Counters)
    psapi = ctypes.windll.psapi
    ok = psapi.GetProcessMemoryInfo(
        process,
        ctypes.byref(counters),
        counters.cb,
    )
    handle_count = wintypes.DWORD()
    ctypes.windll.kernel32.GetProcessHandleCount(
        process,
        ctypes.byref(handle_count),
    )
    if not ok:
        return {"rss": None, "private": None, "handles": int(handle_count.value)}
    return {
        "rss": int(counters.WorkingSetSize),
        "private": int(counters.PrivateUsage),
        "handles": int(handle_count.value),
    }


def _snapshot(label: str):
    dangling = []
    for ref in tuple(getattr(threading, "_dangling", ())):
        thread = ref()
        if thread is not None:
            dangling.append(
                (
                    thread.name,
                    thread.ident,
                    getattr(thread, "native_id", None),
                    thread.is_alive(),
                    thread.daemon,
                )
            )
    resources = _native_resources()
    line = (
        f"label={label} "
        f"pid={os.getpid()} "
        f"python={sys.version.split()[0]} "
        f"allocated_blocks={getattr(sys, 'getallocatedblocks', lambda: None)()} "
        f"gc_count={gc.get_count()} "
        f"rss={resources['rss']} "
        f"private={resources['private']} "
        f"handles={resources['handles']} "
        f"thread_stack_size={threading.stack_size()} "
        f"threads={len(threading.enumerate())} "
        f"active={len(getattr(threading, '_active', {}))} "
        f"limbo={len(getattr(threading, '_limbo', {}))} "
        f"dangling={dangling}"
    )
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()


def pytest_sessionstart(session):
    LOG.write_text("", encoding="utf-8")
    _snapshot("session_start")


def pytest_runtest_protocol(item, nextitem):
    if item.nodeid in TARGETS:
        _snapshot(f"before_{item.nodeid}")
    return None
