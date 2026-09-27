# -*- coding: utf-8 -*-
"""Phase 1B Experiment 05: run the exact adapter test in a fresh process."""

from __future__ import annotations

import os
import platform
import subprocess
import sys


def test_exact_adapter_case_in_fresh_process():
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-vv",
        "--full-trace",
        "tests/test_telegram_runtime_safety.py::TelegramRuntimeSafetyTests::test_adapter_close_stops_xp_writer_thread",
    ]
    env = os.environ.copy()
    env["PYTHONFAULTHANDLER"] = "1"
    env["PYTHONWARNINGS"] = "error::ResourceWarning"

    print(f"PARENT_PYTHON_VERSION={sys.version}")
    print(f"PARENT_PLATFORM={platform.platform()}")

    result = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )
    print("CHILD_STDOUT_BEGIN")
    print(result.stdout)
    print("CHILD_STDOUT_END")
    print("CHILD_STDERR_BEGIN")
    print(result.stderr)
    print("CHILD_STDERR_END")
    print(f"CHILD_RETURN_CODE={result.returncode}")

    assert result.returncode == 0, (
        "The exact TelegramAdapter test did not pass in a fresh Python process."
    )
