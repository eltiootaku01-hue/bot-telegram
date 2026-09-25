from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = (("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD))


def seconds_since_last_input() -> float | None:
    """Return Windows session idle time, or None when it cannot be measured."""
    if os.name != "nt":
        return None

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return None

    # GetTickCount64 is monotonic and avoids wall-clock adjustments.
    ticks_now = ctypes.windll.kernel32.GetTickCount64()
    elapsed_ms = max(0, int(ticks_now) - int(info.dwTime))
    return elapsed_ms / 1000.0


def pc_is_idle(*, threshold_seconds: int = 300) -> bool:
    """True when the current Windows session has been idle long enough."""
    idle_seconds = seconds_since_last_input()
    return idle_seconds is not None and idle_seconds >= threshold_seconds
