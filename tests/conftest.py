# -*- coding: utf-8 -*-
"""Phase 1B Experiment 16: thread-start probes at test-file boundaries."""

from __future__ import annotations

import threading
from pathlib import Path


LOG = Path("phase1b_boundary_probes.log")


def _probe(item):
    state = {"ran": False}

    def worker():
        state["ran"] = True

    thread = threading.Thread(
        target=worker,
        name="phase1b-boundary-probe",
    )
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(
            f"BEFORE file={item.fspath} node={item.nodeid} "
            f"ident={thread.ident} native_id={getattr(thread, 'native_id', None)}\n"
        )
        handle.flush()
        import os
        os.fsync(handle.fileno())

    thread.start()
    thread.join()

    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(
            f"AFTER file={item.fspath} node={item.nodeid} "
            f"ident={thread.ident} native_id={getattr(thread, 'native_id', None)} "
            f"alive={thread.is_alive()} ran={state['ran']}\n"
        )
        handle.flush()
        import os
        os.fsync(handle.fileno())


def pytest_sessionstart(session):
    LOG.write_text("", encoding="utf-8")


def pytest_runtest_teardown(item, nextitem):
    current_file = str(item.fspath)
    next_file = str(nextitem.fspath) if nextitem is not None else None
    if next_file != current_file:
        _probe(item)
