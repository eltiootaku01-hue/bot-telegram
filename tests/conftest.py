# -*- coding: utf-8 -*-
"""Phase 1B Experiment 14: locate native-thread count changes across the suite."""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path


LOG = Path("phase1b_native_thread_timeline.log")
_last_native_threads = None


def _native_thread_count() -> int | None:
    if os.name != "nt":
        return None

    TH32CS_SNAPTHREAD = 0x00000004
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    class ThreadEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", wintypes.LONG),
            ("tpDeltaPri", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
        ]

    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(
        TH32CS_SNAPTHREAD,
        0,
    )
    if snapshot in (0, INVALID_HANDLE_VALUE):
        return None

    try:
        entry = ThreadEntry32()
        entry.dwSize = ctypes.sizeof(ThreadEntry32)
        if not kernel32.Thread32First(snapshot, ctypes.byref(entry)):
            return 0
        count = 0
        pid = os.getpid()
        while True:
            if entry.th32OwnerProcessID == pid:
                count += 1
            if not kernel32.Thread32Next(snapshot, ctypes.byref(entry)):
                break
        return count
    finally:
        kernel32.CloseHandle(snapshot)


def _record(label: str, native_threads: int | None) -> None:
    python_threads = __import__("threading").enumerate()
    line = (
        f"label={label} "
        f"python={sys.version.split()[0]} "
        f"native_threads={native_threads} "
        f"python_threads={len(python_threads)} "
        f"python_thread_names={[t.name for t in python_threads]}"
    )
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        handle.buffer.flush()
        os.fsync(handle.fileno())


def pytest_sessionstart(session):
    global _last_native_threads
    LOG.write_text("", encoding="utf-8")
    _last_native_threads = _native_thread_count()
    _record("session_start", _last_native_threads)


def pytest_runtest_teardown(item, nextitem):
    global _last_native_threads
    current = _native_thread_count()
    if current != _last_native_threads:
        _record(f"after:{item.nodeid}", current)
        _last_native_threads = current
