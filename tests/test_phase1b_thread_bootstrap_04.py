# -*- coding: utf-8 -*-
"""Phase 1B Experiment 04: real PassiveXPTracker bootstrap."""

from __future__ import annotations

import platform
import sys
import tempfile
from pathlib import Path

from bot_ia.interfaces.xp_audit import PassiveXPTracker


def test_passive_xp_tracker_record_message_and_stop():
    print(f"PYTHON_VERSION={sys.version}")
    print(f"PLATFORM={platform.platform()}")

    with tempfile.TemporaryDirectory(prefix="phase1b-tracker-") as directory:
        tracker = PassiveXPTracker(Path(directory) / "xp.sqlite3")
        thread = getattr(tracker, "_thread", None)
        print(
            "AFTER_TRACKER_CREATE "
            f"thread={thread} "
            f"ident={getattr(thread, 'ident', None)} "
            f"native_id={getattr(thread, 'native_id', None)} "
            f"alive={getattr(thread, 'is_alive', lambda: False)()} "
            f"daemon={getattr(thread, 'daemon', None)} "
            f"name={getattr(thread, 'name', None)}"
        )

        result = tracker.record_message("phase1b", "telegram")
        print(f"RECORD_RESULT={result!r}")

        thread = getattr(tracker, "_thread", None)
        print(
            "AFTER_RECORD "
            f"thread={thread} "
            f"ident={getattr(thread, 'ident', None)} "
            f"native_id={getattr(thread, 'native_id', None)} "
            f"alive={getattr(thread, 'is_alive', lambda: False)()} "
            f"daemon={getattr(thread, 'daemon', None)} "
            f"name={getattr(thread, 'name', None)}"
        )

        tracker.stop()

        print(
            "AFTER_STOP "
            f"thread={thread} "
            f"ident={getattr(thread, 'ident', None)} "
            f"native_id={getattr(thread, 'native_id', None)} "
            f"alive={getattr(thread, 'is_alive', lambda: False)()} "
            f"daemon={getattr(thread, 'daemon', None)} "
            f"name={getattr(thread, 'name', None)}"
        )
        assert result.granted is True
        assert thread is not None
        assert thread.is_alive() is False
