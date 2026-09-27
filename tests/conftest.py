# -*- coding: utf-8 -*-
"""Phase 1B validation-only thread lifecycle probe."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path


LOG = Path("phase1b_validation_threads.log")


def _writer_names() -> list[str]:
    return [
        thread.name
        for thread in threading.enumerate()
        if thread.name == "nakama-xp-writer" and thread.is_alive()
    ]


def _write(label: str) -> None:
    LOG.open("a", encoding="utf-8").write(
        f"label={label} python={sys.version.split()[0]} pid={os.getpid()} "
        f"threads={len(threading.enumerate())} writers={len(_writer_names())} "
        f"names={[thread.name for thread in threading.enumerate()]}\n"
    )


def pytest_sessionstart(session):
    LOG.write_text("", encoding="utf-8")
    _write("session_start")


def pytest_sessionfinish(session, exitstatus):
    _write(f"session_finish:{exitstatus}")
