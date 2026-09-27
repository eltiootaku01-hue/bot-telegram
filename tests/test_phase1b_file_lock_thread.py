# -*- coding: utf-8 -*-
"""Phase 1B Experiment 20: Windows filesystem lock operations without os.kill()."""

from __future__ import annotations

import os
import tempfile
import threading


def test_file_lock_ops_without_process_probe_then_thread():
    with tempfile.TemporaryDirectory(prefix="phase1b-file-lock-") as directory:
        path = os.path.join(directory, "telegram.lock")
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(descriptor, b"pid=1\nhost=test\n")
        finally:
            os.close(descriptor)
        os.unlink(path)

    state = {"ran": False}

    def worker():
        state["ran"] = True

    thread = threading.Thread(target=worker, name="phase1b-after-file-lock")
    thread.start()
    thread.join()

    assert state["ran"] is True
    assert thread.is_alive() is False
