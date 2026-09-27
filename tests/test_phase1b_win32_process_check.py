# -*- coding: utf-8 -*-
"""Phase 1B Experiment 20: Win32 process liveness check then Thread."""

from __future__ import annotations

import ctypes
import os
import threading
from ctypes import wintypes


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def test_win32_process_check_then_thread():
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        os.getpid(),
    )
    assert handle
    assert kernel32.CloseHandle(handle)

    state = {"ran": False}

    def worker():
        state["ran"] = True

    thread = threading.Thread(
        target=worker,
        name="phase1b-after-win32-check",
    )
    thread.start()
    thread.join()

    assert state["ran"] is True
    assert thread.is_alive() is False
