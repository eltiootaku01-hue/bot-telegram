# -*- coding: utf-8 -*-
"""Phase 1B Experiment 12: native process-resource snapshot before a new thread."""

from __future__ import annotations

import ctypes
import gc
import os
import platform
import sys
import threading
from ctypes import wintypes
from pathlib import Path


LOG = Path("phase1b_native_resources.log")


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
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry32)]
    kernel32.Thread32First.restype = wintypes.BOOL
    kernel32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry32)]
    kernel32.Thread32Next.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    snapshot = kernel32.CreateToolhelp32Snapshot(
        TH32CS_SNAPTHREAD,
        0,
    )
    if snapshot in (0, INVALID_HANDLE_VALUE):
        return None

    try:
        entry = ThreadEntry32()
        entry.dwSize = ctypes.sizeof(ThreadEntry32)
        count = 0
        if not kernel32.Thread32First(snapshot, ctypes.byref(entry)):
            return 0
        pid = os.getpid()
        while True:
            if entry.th32OwnerProcessID == pid:
                count += 1
            if not kernel32.Thread32Next(snapshot, ctypes.byref(entry)):
                break
        return count
    finally:
        kernel32.CloseHandle(snapshot)


def _process_resources() -> dict[str, int | None]:
    if os.name != "nt":
        return {"rss": None, "private": None, "handles": None}

    class CountersEx(ctypes.Structure):
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
    psapi = ctypes.windll.psapi
    counters = CountersEx()
    counters.cb = ctypes.sizeof(CountersEx)
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
        return {
            "rss": None,
            "private": None,
            "handles": int(handle_count.value),
        }
    return {
        "rss": int(counters.WorkingSetSize),
        "private": int(counters.PrivateUsage),
        "handles": int(handle_count.value),
    }


def _snapshot(label: str) -> None:
    dangling = []
    for thread in tuple(getattr(threading, "_dangling", ())):
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

    resources = _process_resources()
    line = (
        f"label={label} "
        f"pid={os.getpid()} "
        f"python={sys.version.split()[0]} "
        f"platform={platform.platform()} "
        f"allocated_blocks={getattr(sys, 'getallocatedblocks', lambda: None)()} "
        f"gc_count={gc.get_count()} "
        f"rss={resources['rss']} "
        f"private={resources['private']} "
        f"handles={resources['handles']} "
        f"python_threads={len(threading.enumerate())} "
        f"native_threads={_native_thread_count()} "
        f"active={len(getattr(threading, '_active', {}))} "
        f"limbo={len(getattr(threading, '_limbo', {}))} "
        f"dangling_count={len(dangling)} "
        f"dangling={dangling}"
    )
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def pytest_sessionstart(session):
    LOG.write_text("", encoding="utf-8")
    _snapshot("session_start")


def pytest_runtest_setup(item):
    if item.name != "test_adapter_close_stops_xp_writer_thread":
        return

    _snapshot("before_target_thread_bootstrap")

    state = {"ran": False}

    def worker():
        state["ran"] = True

    thread = threading.Thread(
        target=worker,
        name="phase1b-pretarget-minimal",
    )
    thread.start()
    thread.join()
    assert state["ran"] is True
